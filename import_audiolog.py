import cgi
import glob
import os
import re
import sqlite3
import tarfile
from naomi import paths
from naomi import plugin


class ImportAudiologPlugin(plugin.STTTrainerPlugin):
    def HandleCommand(self, **kwargs):
        command=kwargs['command']
        description=kwargs['description']
        fields=kwargs['fields']
        conn = kwargs['conn']
        response = []
        try:
            audiolog_dir = paths.sub("audiolog")
            if(command==""):
                # Create the form for uploading an audiolog file
                response.append('''<script type="text/javascript">''')
                response.append('''function submitForm(){''')
                response.append('''    var file = document.getElementById('file').files[0];''')
                response.append('''    var formData = new FormData();''')
                response.append('''    formData.append('file', file, file.name);''')
                response.append('''    var xhr = new XMLHttpRequest();''')
                response.append('''    xhr.open('POST', location.toString(), true);''')
                response.append('''    xhr.onload = function () {''')
                response.append('''        if (xhr.status == 200) {''')
                response.append('''            document.getElementById("Result").innerHTML = 'Upload copmlete!';''')
                response.append('''        } else {''')
                response.append('''            document.getElementById("Result").innerHTML = 'Upload error. Try again.';''')
                response.append('''        }''')
                response.append('''    };''')
                response.append('''    xhr.send(formData);''')
                response.append('''    return false;''')
                response.append('''}''')
                response.append('''</script>''')
                response.append('''<form id="form" method="post" onsubmit="var file = document.getElementById('myfile').files[0]; var formData = new FormData(); formData.append('engine', 'Import Audiolog'); formData.append('command', 'processArchive'); formData.append('file', file, file.name); var xhr = new XMLHttpRequest(); xhr.onload = function () { if (xhr.status == 200) {var response=JSON.parse(this.responseText); document.getElementById('Result').innerHTML += response.message; } else { document.getElementById('Result').innerHTML += 'Upload error. Try again.'; } }; xhr.open('POST', location.toString(), true); xhr.send(formData); return false;" enctype="multipart/form-data">''')
                response.append('''<input type="hidden" name="engine" value="Import Audiolog"/>''')
                response.append('''<label for="file">Archive file:</label><input id="myfile" name="file" type="file" accept=".tgz"/><br />''')
                response.append('''<input type="submit" value="Submit"/>''')
                response.append('''</form>''')
            if(command=="processArchive"):
                fileitem = fields['file']
                filepath=os.path.join(audiolog_dir,'audiolog.tgz')
                with open(filepath, 'wb') as f:
                    f.write(fileitem.file.read())
                response.append('Saved file as {}<br />\n'.format(filepath))
                # extract the audiolog_temp.db file
                try:
                    with tarfile.open(filepath, mode="r:gz") as archive_file:
                        audiolog_temp_path = os.path.join(audiolog_dir, 'audiolog_temp.db')
                        with open(audiolog_temp_path, 'wb') as f:
                            f.write(archive_file.extractfile('audiolog_temp.db').read())
                        response.append("extracted audiolog_temp.db")
                        # Now open the audiolog_temp database with sqlite3
                        temp_conn = sqlite3.connect(audiolog_temp_path)
                        temp_conn.row_factory = sqlite3.Row
                        query = " ".join([
                            "select",
                            "   datetime,",
                            "   engine,",
                            "   filename,",
                            "   type,",
                            "   transcription,",
                            "   verified_transcription,",
                            "   speaker,",
                            "   reviewed,",
                            "   wer,",
                            "   intent,",
                            "   score,",
                            "   verified_intent,",
                            "   tti_engine",
                            "from audiolog"
                        ])
                        for row in temp_conn.execute(query):
                            # If filename does not exist in the filesystem
                            wavfile_path = os.path.join(audiolog_dir, row['filename'])
                            if(not os.path.isfile(wavfile_path)):
                                response.append("extracting {}<br />\n".format(row['filename']))
                                with open(wavfile_path, 'wb') as f:
                                    f.write(archive_file.extractfile(row['filename']).read())
                                response.append('Extracted {}'.format(wavfile_path))
                            # we don't want to create a whole bunch of
                            # duplicate records. I think the filename,
                            # type and transcription should be enough
                            # to tell whether this is a duplicate or not.
                            if not conn.execute(
                                " ".join([
                                    'select exists (',
                                    '   select 1',
                                    '       from audiolog',
                                    '   where filename=?',
                                    '       and type=?',
                                    '       and transcription=?',
                                    ')'
                                ]),
                                (
                                    row['filename'],
                                    row['type'],
                                    row['transcription']
                                )
                            ).fetchone()[0]:
                                # Insert the current line into audiolog
                                conn.execute(
                                    " ".join([
                                        "insert into audiolog(",
                                        "   datetime,",
                                        "   engine,",
                                        "   filename,",
                                        "   type,",
                                        "   transcription,",
                                        "   verified_transcription,",
                                        "   speaker,",
                                        "   reviewed,",
                                        "   wer,",
                                        "   intent,",
                                        "   score,",
                                        "   verified_intent,",
                                        "   tti_engine",
                                        ")values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                                    ]),
                                    (
                                        row['datetime'],
                                        row['engine'],
                                        row['filename'],
                                        row['type'],
                                        row['transcription'],
                                        row['verified_transcription'],
                                        row['speaker'],
                                        row['reviewed'],
                                        row['wer'],
                                        row['intent'],
                                        row['score'],
                                        row['verified_intent'],
                                        row['tti_engine']
                                    )
                                )
                                response.append("Added row to audiolog<br />\n")
                                conn.commit()
                    response.append("Finished importing archive")
                except KeyError:
                    response.append("could not extract audiolog_temp.db")
        except Exception as e:
            continue_next = False
            message = "Unknown"
            if hasattr(e, "message"):
                message = e.message
            self._logger.error(
                "Error: {}".format(
                    message
                ),
                exc_info=True
            )
            response.append('<span class="failure">{}</span>'.format(
                message
            ))
        return response, "", ""
        
