__author__ = "Nemes"

import json
import subprocess
import datetime

def convert(value):
    if value > (1024*1024*1024*5):
        return "{0:.2f}".format(value / (1024*1024*1024)) + " TiB"
    elif value > (1024*1024*5):
        return "{0:.2f}".format(value / (1024*1024)) + " GiB"
    elif value > (1024*5):
        return "{0:.2f}".format(value / 1024) + " MiB"
    else:
        return "{0:.2f}".format(value) + " KiB"

def notify(header, message):
    subprocess.call("/bin/bash send.sh \"" + header + "\" \"" + message + "\"", shell=True)

def get_file_size(source, destination, dir):
    cmd = ""
    if destination is None:
        cmd = "du -s " + dir
    else:
        cmd = "/usr/bin/ssh " + destination + " \"du -s " + dir + "\""
    if source is not None:
        cmd = "/usr/bin/ssh " + source + " '" + cmd + "'"
    out, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    ret = str(out)
    size = 0
    try:
        size = int(ret[2:ret.index('\\t')])
    except:
        size = 0
    print("        " + dir + " (" + convert(size) + ")")
    return size

def get_source_size(source, destination, directories):
    size = 0
    for dir in directories:
        size += get_file_size(source, destination, dir);
    return size

def get_free_space(source, destination, dir):
    cmd = ""
    if destination is None:
        cmd = "echo $(($(stat -f --format=%a*%S " + dir + ")))"
    else:
        if source is None:
            cmd = "/usr/bin/ssh " + destination + " 'echo $(($(stat -f --format=%a*%S " + dir + ")))'"
        else:
            cmd = "/usr/bin/ssh " + destination + " \\\\'echo \\\\\\$\\\\\\(\\\\\\(\\\\\\$\\\\\\(stat -f --format=%a*%S " + dir + "\\\\\\)\\\\\\)\\\\\\)\\\\'"
    if source is not None:
        cmd = "/usr/bin/ssh " + source + " '" + cmd + "'"
    out, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return int(out) / 1024

def is_online(source, destination):
    cmd = ""
    if destination is None:
        cmd = "exit"
    else:
        cmd = "/usr/bin/ssh " + destination + " \"exit\""
    if source is not None:
        cmd = "/usr/bin/ssh " + source + " '" + cmd + "'"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return proc.returncode != 255

def is_available(source, destination, lockfile):
    cmd = ""
    if destination is None:
        cmd = "stat " + lockfile
    else:
        cmd = "/usr/bin/ssh " + destination + " \"stat " + lockfile + "\""
    if source is not None:
        cmd = "/usr/bin/ssh " + source + " '" + cmd + "'"
    out, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return str(out) == "b''"

def run_backup(borg, snapshot_name, source, destination, directories, destination_dir):
    if borg:
        dirlist = " ".join(directories)
        snapshot_name += datetime.datetime.now().strftime("_%Y-%m-%d_%H:%M:%S")
    else:
        dirlist = " --include ".join(directories)
    cmd = ""
    if borg:
        if destination is None:
            cmd = "borg create -C zlib,6 " + destination_dir + "::" + snapshot_name + " " + dirlist
        else:
            cmd = "borg create -C zlib,6 " + destination + ":" + destination_dir + "::" + snapshot_name + " " + dirlist
    else:
        if destination is None:
            cmd = "rdiff-backup --include " + dirlist + " --exclude / / " + destination_dir
        else:
            cmd = "rdiff-backup --include " + dirlist + " --exclude / / " + destination + "::" + destination_dir
    if source is not None:
        cmd = "/usr/bin/ssh " + source + " '" + cmd + "'"
    print(cmd + "\n")
    subprocess.call(cmd, shell=True)

def backup_computer(comp):
    print("Backing up " + comp["source-name"])
    source = comp["source"]
    dest = comp["destination"]
    name = comp["source-name"]
    dst_name = comp["destination-name"]
    borg = comp["use-borg"]
    remote_src = None
    remote_dst = None
    destination = None
    if 'remote:' in source:
        remote_src = source[source.find(':')+1:len(source)]
    if ':' in dest:
        remote_dst = dest[0:dest.find(':')]
        destination = dest[dest.find(':')+1:len(dest)]
    else:
        destination = dest;
    if borg:
        print("    Using: borgbackup")
    else:
        print("    Using: rdiff-backup")
    print("    Source: " + (name if remote_src is None else ("ssh:" + name)))
    print("    Destination: " + (name if remote_dst is None else ("ssh:" + dst_name)) + " " + destination)
    src_online = is_online(None, remote_src)
    if not src_online:
        print("    Source " + name + " is offline!")
        notify("Backup of " + name + " Failed", "Backup source is offline")
        return
    dst_online = is_online(remote_src, remote_dst)
    if not dst_online:
        print("    Destination " + dst_name + " is offline!")
        notify("Backup of " + name + " Failed", "Backup destination " + dst_name + " is offline")
        return
    dst_avail = is_available(remote_src, remote_dst, comp["lock-file"])
    if not dst_avail:
        print("    Destination " + dst_name + " is not available!")
        notify("Backup of " + name + " Failed", "Backup destination " + dst_name + " is not available")
        return
    print("    Directories:")
    src_size = get_source_size(remote_src, None, comp["directories"])
    notify("Backup of " + name + " Starting", "Source size: " + convert(src_size))
    print("    Destination Size:")
    diff = get_file_size(remote_src, remote_dst, destination)
    print("    Backup Command:\n")
    run_backup(borg, name, remote_src, remote_dst, comp["directories"], destination)
    print("\n    Destination Size:")
    dst_size = get_file_size(remote_src, remote_dst, destination);
    diff = dst_size - diff;
    print("    Backup Difference: " + convert(diff))
    free = get_free_space(remote_src, remote_dst, destination)
    print("    Destination Free Space: " + convert(free))
    notify("Backup of " + name + " Finished", "Destination size: " + convert(dst_size) + "\nBackup difference: " + convert(diff) + "\n" + dst_name + " free space: " + convert(free))
    return

config_file = open("config.json", "r")
config = json.loads(config_file.read())

for computer in config:
    backup_computer(computer)
