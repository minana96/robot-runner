from io import TextIOWrapper
import os
import re
import textwrap
from typing import List
from paramiko.sftp_file import SFTPFile


class LogFileProfiler:

    def __init__(self, ip_addr = "", username = "", hostname = "") -> None:
        self.ip_addr = ip_addr
        self.username = username
        self.hostname = hostname
        self.path_to_local_log_folder = f"/home/{os.environ['USERNAME']}/.ros/log/latest"
        self.path_to_remote_log_folder = f"/home/{self.username}/.ros/log/latest"

    def get_remote_log_file_names(self, ssh_client) -> List:
        # cd to the latest ros log folder
        channel = ssh_client.invoke_shell()
        stdin = channel.makefile('wb')
        stdout = channel.makefile('rb')

        commands = textwrap.dedent('''\
        cd .ros/log/latest
        ls
        exit
        ''')

        stdin.write(commands)

        # Extract the result of the ls command
        result = stdout.read().decode("utf8")

        log_file_names = result[result.index(f'{self.username}@{self.hostname}:~/.ros/log/latest$ ls') + 
                                len(f'{self.username}@{self.hostname}:~/.ros/log/latest$ ls') : 
                                result.index(f'{self.username}@{self.hostname}:~/.ros/log/latest$ exit')]

        stdout.close()
        stdin.close()
        channel.close()
        return log_file_names.split()

    def open_remote_log_file(self, ssh_client, sftp_client, node_name) -> SFTPFile:
        # Get names of all log files on a remote machine
        log_file_names = self.get_remote_log_file_names(ssh_client)

        for file_name in log_file_names:
            # Find the log file of the requested node
            if re.fullmatch(f"{node_name}-[0-9]+-stdout.log", file_name) or re.fullmatch(f"{node_name}-[0-9].log", file_name):
                # Transfer the file over SFTP
                log_file = sftp_client.open(os.path.join(self.path_to_remote_log_folder, file_name), 'r')
                log_file.prefetch()
                return log_file

        # File not found, close SSH connection
        raise FileNotFoundError(f"Log file of the node '{node_name}' not found!")

    def get_local_log_file_names(self) -> List:
        log_files = [f for f in os.listdir(self.path_to_local_log_folder) if os.path.isfile(os.path.join(self.path_to_local_log_folder, f))]
        return log_files

    def open_local_log_file(self, node_name) -> TextIOWrapper:
        log_file_names = self.get_local_log_file_names()

        for file_name in log_file_names:
            # Find the log file of the requested node
            if re.fullmatch(f"{node_name}-[0-9]+-stdout.log", file_name) or re.fullmatch(f"{node_name}-[0-9].log", file_name):
                file = open(os.path.join(self.path_to_local_log_folder, file_name), 'r')
                return file

        # File not found
        raise FileNotFoundError(f"Log file of the node '{node_name}' not found!")


