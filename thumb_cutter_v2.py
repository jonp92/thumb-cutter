#! /usr/bin/python
import os
import base64
import re
import time
import configparser
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FileHandler(FileSystemEventHandler):
    # watchdog monitors for new .gcode files being created, if it is a directory creation it is ignored.
    def on_created(self, event):
        if event.is_directory:
            return

        # if a .gcode file is created, read in the file to data variable

        if event.src_path.endswith('.gcode'):
            with open(event.src_path, 'r') as f:
                data = f.read()

            # regex pattern to find data between thumbnail begin 500x500 plus any number 5 digits or longer
            # and thumbnail end. Then sub out all ; for "" and pipe data into base64 to be decoded
            # and stored in thumbnail_data.

            pattern = r'; thumbnail begin 500x500 \d{5,}(.+); thumbnail end'
            match = re.search(pattern, data, re.DOTALL)
            if match:
                thumbnail_data = match.group(1).strip()
                thumbnail_data = re.sub(r'^; ', '', thumbnail_data, flags=re.MULTILINE)
                thumbnail_data = base64.b64decode(thumbnail_data)

                # Then write the file and print a success message.
                output_path = os.path.join(output_dir, f'{tmpfilename}.png')

                with open(output_path, 'wb') as f:
                    f.write(thumbnail_data)
                print(f'Saved thumbnail as {output_path}')

                # Copy the file to the remote server using scp
                scp_command = ['scp', '-P', port, output_path, f'{username}@{server}:{remote_dir}']
                subprocess.run(scp_command)


# this method preprocesses any existing file in the input_dir and uploads then to a directory.

def create_thumbnails():
    for filename in os.listdir(input_dir):
        if filename.endswith('.gcode'):
            input_path = os.path.join(input_dir, filename)
            with open(input_path, 'r') as f:
                data = f.read()

            pattern = r'; thumbnail begin 500x500 \d{5,}(.+); thumbnail end'
            match = re.search(pattern, data, re.DOTALL)
            if match:
                thumbnail_data = match.group(1).strip()
                thumbnail_data = re.sub(r'^; ', '', thumbnail_data, flags=re.MULTILINE)
                thumbnail_data = base64.b64decode(thumbnail_data)

                # Find the filename from the gcode between ;filename:example.gcode/ Save this and document.
                pattern = r';filename:(.+?)/'
                match = re.search(pattern, data)
                if match:
                    filename = match.group(1).strip()
                    output_path = os.path.join(preprocess_dir, filename + '.png')

                    with open(output_path, 'wb') as f:
                        f.write(thumbnail_data)
                    print(f'Saved thumbnail as {output_path}')

                # Copy the file to the remote server using scp
                    scp_command = ['scp', '-P', port, output_path, f'{username}@{server}:{remote_dir}']
                    subprocess.run(scp_command)


if __name__ == '__main__':
    # Read the configuration file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Get the directory paths from the configuration file
    input_dir = config.get('directories', 'input_dir')
    output_dir = config.get('directories', 'output_dir', fallback='~/.thumb_cutter/thumbs')
    preprocess_dir = config.get('directories', 'preprocess_dir', fallback='~/.thumb_cutter/thumbs')

    # Get scp username, server, remote_dir, and port
    username = config.get('remote', 'username')
    server = config.get('remote', 'server')
    remote_dir = config.get('remote', 'remote_dir')
    port = config.get('remote', 'port', fallback='22')

    # get filename for moonraker workaround
    tmpfilename = config.get('output', 'filename', fallback='thumbnail')

    # Create the output directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(preprocess_dir, exist_ok=True)

    # Create thumbnails for all existing files in the input directory
    create_thumbnails()

    # Create the FileHandler and Observer objects
    event_handler = FileHandler()
    observer = Observer()

    # Schedule the observer to monitor the input directory
    observer.schedule(event_handler, input_dir, recursive=True)

    # Start the observer
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
