#!/usr/bin/env python3
import contextlib

__author__ = ""

# This python script encodes all video files present in the inputs folder
# to the optimal resolutions for the selected VR platforms

# check if minimum version of python is version 3
# import sys
# if sys.version_info.major < 3:
#     exit("Python 3 required, exiting.")

# DPX to h.264: ffmpeg -y -start_number 0101 -i \\path\to\filename.%04d.dpx -vf colormatrix=bt601:bt709 -pix_fmt yuv420p sample.mp4

import subprocess, os, sys, errno
import tkinter.filedialog as tkFileDialog
import math
from tkinter import *
from tkinter.ttk import Progressbar
import tkinter.messagebox
import webbrowser
from _thread import start_new_thread

OS = os.name

if getattr(sys, 'frozen', False):
    # frozen
    cwd = os.path.dirname(sys.executable)

    if OS == "nt":

        # _MEIPASS is Pyinstaller's temp directory
        if hasattr(sys, "_MEIPASS"):
            FFPROBE_PATH = os.path.join(sys._MEIPASS, 'Resources', 'ffprobe3.exe')
            FFMPEG_PATH = os.path.join(sys._MEIPASS, 'Resources', 'ffmpeg3.exe')
        else:
            FFMPEG_PATH = os.path.join(cwd, 'Resources', 'ffmpeg3.exe')
            FFPROBE_PATH = os.path.join(cwd, 'Resources', 'ffprobe3.exe')

    elif OS == "mac" or OS == "posix":
        FFMPEG_PATH = os.path.dirname(cwd) + '/Resources/ffmpeg'
        FFPROBE_PATH = os.path.dirname(cwd) + '/Resources/ffprobe'
else:
    # unfrozen
    cwd = os.path.dirname(os.path.realpath(__file__))
    if OS == "nt":
        FFMPEG_PATH = cwd + '/ffmpeg3.exe'
        FFPROBE_PATH = cwd + '/ffprobe3.exe'

    elif OS == "mac" or OS == "posix":
        FFMPEG_PATH = 'ffmpeg'
        FFPROBE_PATH = 'ffprobe'

# Write stdout to logfile
sys.stdout = open(cwd + '/vrencoder_log.txt', 'w', 1)
sys.stderr = open(cwd + '/vrencoder_errors.txt', 'w', 1)
fps_input = ""


class StatusBar(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.label = Label(self, bd=1, relief=SUNKEN, anchor=W)
        self.label.grid(row=18, columnspan=3, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(18, weight=1)

    def set(self, format, *args):
        self.label.config(text=format % args)
        self.label.update_idletasks()

    def clear(self):
        self.label.config(text="")
        self.label.update_idletasks()


class FPSDialog:
    def __init__(self, parent):
        self.sequence_fps = StringVar()
        top = self.top = Toplevel(parent)

        Label(top, text="What is the FPS of your sequence?").grid(row=1, column=1, columnspan=2, padx=5, pady=5,
                                                                  sticky=W)

        self.e = Entry(top)
        self.e.grid(row=2, column=1, padx=5, pady=5, sticky=E)

        b = Button(top, text="OK", command=self.ok)
        b.grid(row=2, column=2, padx=5, pady=5, sticky=E)

    def ok(self):
        print("Sequence FPS = ", self.e.get())
        if not self.e.get():
            tkinter.messagebox.showinfo("Uh oh!", "Please fill in the FPS of your sequence first")
        else:
            self.sequence_fps = self.e.get()
            self.top.destroy()


# This class runs the ffmpeg commands and tracks progress
class FFMpegRunner(object):

    def __init__(self, input_file, fps_input, fps_output, sequence):
        self.input_file = input_file
        self.fps_input = float(fps_input)
        self.fps_output = float(fps_output)
        if sequence:
            sequence_counter = 0
            filelist = os.listdir(input_dir_path)
            for file in filelist:
                if file.endswith(('.dpx', '.exr', '.tif', '.tiff')):
                    sequence_counter += 1
            self.frames_number = sequence_counter
        else:
            self.frames_number = self._get_frame_numbers()

    def _get_frame_numbers(self):
        command = [
            FFPROBE_PATH,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            self.input_file
        ]
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        nb_frames = proc.stdout.readline().rstrip()
        if any(char.isdigit() for char in nb_frames):
            return int(nb_frames)
        else:
            # If codec does not contain nb_frames, use duration
            command = [
                FFPROBE_PATH,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                self.input_file
            ]
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                universal_newlines=True
            )
            duration = proc.stdout.readline().rstrip()
            nb_frames = float(duration) * self.fps_input
            return int(nb_frames)

    def run_session(self, command, status_handler=None):
        pipe = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        percents = 0
        while True:
            line = pipe.stdout.readline().rstrip()
            #print(line)
            # Line is no string, ouput is [''] so line == '' check doesn't do anything
            if pipe.poll() is not None:
                print("Subprocess return something -> done: %s" % line)
                break
            print(str(line))
            if len(line.split("=")) > 2:
                current_frame = int(line.split("=")[1].split()[0].strip())
                encoding_fps = float(line.split("=")[2].split()[0].strip())
                output_frames_number = (self.frames_number / self.fps_input) * self.fps_output
                # print("Output frames number = "+str(output_frames_number))
                # time_elapsed = line.split("=")[5].split()[0].strip()
                # print("Current frame = "+str(current_frame))
                # print("Encoding fps = "+str(encoding_fps))
                # print("Time elapsed = "+str(time_elapsed))

                if encoding_fps > 0.0:
                    # print("self.frames_number = %s" % self.frames_number)
                    if (output_frames_number - current_frame != 0):
                        time_remaining = (output_frames_number - current_frame) / encoding_fps
                        if (time_remaining < 0):
                            time_remaining = 0
                    else:
                        time_remaining = 0

                    # time_remaining = (self.frames_number-current_frame)/encoding_fps
                    # print("Time remaining = %s" % time_remaining)
                    m, s = divmod(time_remaining, 60)
                    h, m = divmod(m, 60)
                    time_remaining_label.config(text="Time remaining: %d:%02d:%02d" % (h, m, s))
                    # print("Time remaining = %d:%02d:%02d" % (h, m, s))

                new_percents = self._get_percent(current_frame, output_frames_number)
                if new_percents != percents:
                    if callable(status_handler):
                        status_handler(percents, new_percents)
                    percents = new_percents

    def _get_percent(self, current_frame, output_frames_number):
        # percent = int(math.floor(100 * current_frame/self.frames_number))
        percent = int(math.floor(100 * current_frame / output_frames_number))
        return 0 if percent >= 100 else percent


# -------------------------------------------------------------------------------
# CONFIGURABLE SETTINGS
# -------------------------------------------------------------------------------

# codec (h264, h265)
CODEC = 'h264'

# controls the quality of the encode (18 - 23, lower value = higher quality/bigger file size)
CRF_VALUE = '19'

# h.264/h.265 profile (baseline, main, high)
PROFILE = 'baseline'

LEVEL = '4.2'

# encoding speed:compression ratio (slow, medium, fast)
PRESET = 'medium'


# -------------------------------------------------------------------------------
# encoding script
# -------------------------------------------------------------------------------


# Start a new thread to run the encoding in
def start_thread():
    # Make sure an input and output folder are selected
    if input_filename_left.get() == "" or input_filename_right.get() == "" or output_dir.get() == "":
        tkinter.messagebox.showinfo("Uh oh!", "Please select an input files and output folder first!")
    else:
        start_new_thread(check_platforms, ())


# Synchronise left & right clip
def synchronise(left_file, right_file):
    left_audio = left_file.split(".")[0] + ".wav"
    right_audio = right_file.split(".")[0] + ".wav"

    status_bar.set("Extracting audio...")
    command = "ffmpeg -i {0} -map 0:1 -acodec pcm_s16le -ac 2 {1}".format(right_file, right_audio)
    os.system(command)
    command = "ffmpeg -i {0} -map 0:1 -acodec pcm_s16le -ac 2 {1}".format(left_file, left_audio)
    os.system(command)
    status_bar.set("Calculating offset...")

    result = subprocess.run(["praat", "--run", "crosscorrelate.praat", left_audio, right_audio],
                            stdout=subprocess.PIPE).stdout.decode('utf-8')
    offset = round(float(result), 3)

    status_bar.set("Offset :" + result)
    command = "rm {0} {1}".format(left_audio, right_audio)
    os.system(command)

    if -0.002 <= offset <= 0.002:
        status_bar.set("Files are already synced. ")
        return left_file, right_file
    elif offset > 0:
        synced_file = truncate(right_file, offset)
        status_bar.set("Syncing done.")
        return left_file, synced_file
    else:
        synced_file = truncate(left_file, offset)
        status_bar.set("Syncing done.")
        return synced_file, right_file


def truncate(file_to_truncate, offset):
    status_bar.set("Syncing files...")
    filename, file_extension = os.path.splitext(file_to_truncate)
    synced_filename = filename + '_sync' + file_extension
    with contextlib.suppress(FileNotFoundError):
        os.remove(synced_filename)
    command = "ffmpeg -i {0} -ss {1} -c:v copy -c:a copy {2}".format(
        file_to_truncate,
        abs(offset),
        synced_filename)
    os.system(command)
    return synced_filename


# Check which platforms are selected
def check_platforms():
    print("Checking platforms")
    number_of_platforms = 0
    current_thread = 0
    for x in range(len(selected_platforms)):
        platform_state = selected_platforms[x][1].get()
        if platform_state == 1:
            number_of_platforms += 1
    print("Number of platforms selected = " + str(number_of_platforms))

    for x in range(len(selected_platforms)):
        current_platform = selected_platforms[x][0]
        platform_state = selected_platforms[x][1].get()
        print(current_platform + " = " + str(platform_state))

        # Start encoding for the current platform if selected
        # Create new thread to run the process() function

        if platform_state == 1:
            # start_new_thread(process, (current_platform, number_of_platforms))
            process(current_platform, number_of_platforms)

            current_thread += 1

    # Show message when all encodes are finished
    status_bar.set("Finished encoding all files!")

    # Reset fps_output
    global fps_input
    fps_input = ""


def process(current_platform, number_of_platforms):
    # get a list of files from the inputs folder
    # filelist = os.listdir(cwd+'/inputs')
    # count total number of video files to encode
    number_of_files = 0
    sequence = False

    if input_filename_left.get() != "" and input_filename_right.get() != "":
        # encode a stereoscopic file from left and right videos
        metadata = mediainfo(input_filename_left.get())
        # Show progress message
        status_bar.set(
            current_platform + ": encoding stereoscopic file LEFT["
            + input_filename_left.get() + "] RIGHT["
            + input_filename_right.get() + "]"
        )
        # Syncing files
        do_synchronisation = False
        if do_synchronisation:
            left_file, right_file = synchronise(input_filename_left.get(), input_filename_right.get())
        else:
            left_file = input_filename_left.get()
            right_file = input_filename_right.get()

        # Start encoding this file
        status_bar.set("Start encoding of stereoscopic file...")
        encode(left_file, metadata, current_platform, sequence, right_file)

    else:
        filelist = os.listdir(input_dir_path)
        for file in filelist:
            # IF it has one of the following extensions
            if file.endswith(('.dpx', '.exr', '.tif', '.tiff')):
                sequence = True
                number_of_files = 1
            elif file.endswith(('.mov', '.mpg', '.mp4', '.MP4', '.wmv', '.avi', '.webm')):
                number_of_files += 1

        print("Number of input files = " + str(number_of_files))
        total_files = number_of_files * number_of_platforms
        print("Total video files to encode = " + str(total_files))

        file_number = 0

        # encode sequence..
        if sequence:
            firstfile = ""
            firstfile_found = False
            for file in filelist:
                if (firstfile_found == False and not file.startswith(".")):
                    firstfile = file
                    firstfile_found = True
                else:
                    continue

            print('First file = ' + firstfile)
            filepath = os.path.join(input_dir_path, firstfile)
            metadata = mediainfo(filepath)
            print(metadata)
            # Show progress message
            status_bar.set(current_platform + ": encoding sequence")
            # Start encoding this file
            encode(firstfile, metadata, current_platform, sequence, None)

        else:
            # encode each file..
            for file in filelist:
                # IF it has one of the following extensions
                if file.endswith(('.mov', '.mpg', '.mp4', '.MP4', '.wmv', '.avi', '.webm')):
                    file_number += 1
                    print('File = ' + file)
                    filepath = os.path.join(input_dir_path, file)
                    metadata = mediainfo(filepath)
                    # Show progress message
                    status_bar.set(current_platform + ": encoding file " + str(file_number) + " of " + str(number_of_files))
                    # Start encoding this file
                    encode(file, metadata, current_platform, sequence, None)
                else:
                    print(
                        file + " is not an accepted video file (.mov, .avi, .mp4, .wmv, .mpg, .webm, .dpx, .exr, .tif, .tiff)")


# Get video metadata
def mediainfo(filepath):
    print("Filepath = " + filepath)

    # get video metadata
    result = subprocess.Popen([FFPROBE_PATH, '-show_streams', '-select_streams', 'v:0', '-i', filepath],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = result.communicate()
    out = out.decode('utf-8')  # Decode Byte-string to Unicode string
    print(out)

    # Store metadata in variables
    metadata = {}
    for line in out.splitlines():
        if '=' in line and not 'configuration' in line:
            key, value = line.split('=')
            metadata[key] = value
    print("Metadata = ")
    print(metadata)

    return metadata


# Determine optimal FPS for output
def find_fps(fps_rounded, max_fps):
    fps_rounded = float(fps_rounded)
    if fps_rounded > max_fps:
        # Scale down fps
        if fps_rounded % 29.97 == 0 and max_fps <= 30:
            fps_output = "29.97"
        elif fps_rounded % 29.97 == 0 and max_fps <= 60:
            fps_output = "59.94"
        elif fps_rounded % 30 == 0 and max_fps <= 30:
            fps_output = "30"
        elif fps_rounded % 30 == 0 and max_fps <= 60:
            fps_output = "60"
        else:
            fps_output = "30"
    else:
        fps_output = str(fps_rounded)

    print("FPS output = " + fps_output)
    return fps_output


# Encode all videos
def encode(file, metadata, current_platform, sequence, right_file):
    global fps_input

    print("encode() function, platform =")
    print(current_platform)
    if sequence:
        if fps_input == "":
            dialog = FPSDialog(root)
            dialog.top.lift()
            root.wait_window(dialog.top)
            fps_input = str(dialog.sequence_fps)
        fps_output = fps_input
        fps_rounded = fps_input
        print("fps_input = " + fps_input)
        print("fps_rounded = " + fps_rounded)
        # vfilter = "colormatrix=bt601:bt709,"
        vfilter = ""
    else:
        print("FPS = " + metadata["r_frame_rate"])
        fps_split = metadata["r_frame_rate"].split("/")
        print(fps_split)
        fps = int(fps_split[0]) / int(fps_split[1])
        print(fps)
        fps_rounded = round(fps, 2)
        print(fps_rounded)
        fps_output = str(fps_rounded)
        vfilter = ""

    # Store metadata in variables
    width = metadata["width"]
    print("Width = " + width)
    height = metadata["height"]
    print("Height = " + height)
    aspect_ratio = metadata["display_aspect_ratio"]
    print("Aspect ratio = " + aspect_ratio)

    # Set default values
    bitrate = "13M"
    minrate = "8M"
    maxrate = "15M"
    audio_bitrate = "192k"
    crf = "19"

    aspect_calculated = int(width) / int(height)
    print("Calculated aspect ratio = " + str(aspect_calculated))

    # Creating a stereoscopic file by vertical stacking left and right videos
    if right_file is not None:
        aspect_calculated = int(width) / (int(height) * 2)
        aspect_ratio = "1:1"

    # Platform encoding settings
    # 1.77777 = 16:9
    if aspect_calculated == 1.0 and current_platform == "Stereo2Mono":
        aspect_ratio = "2:1"
    # elif aspect_calculated != 1.0 and current_platform == "Stereo2Mono":
    #    tkinter.messagebox.showinfo("Uh oh!", "You did not select a stereo video with a 1:1 aspect ratio as input")
    elif aspect_calculated == 1.0:
        aspect_ratio = "1:1"
    elif aspect_calculated == 2.0:
        aspect_ratio = "2:1"
    else:
        aspect_ratio = aspect_calculated

    if current_platform == "Desktop VR":
        platform_name = "desktopvr"
        codec = "vp9"
        audio_bitrate = "320k"
        max_fps = 60
        fps_output = find_fps(fps_rounded, max_fps)
        if (float(fps_output) > 30):
            bitrate = "26M"
            minrate = "16M"
            maxrate = "30M"
        else:
            bitrate = "13M"
            minrate = "8M"
            maxrate = "15M"
    elif current_platform == "Android VP9":
        platform_name = "android"
        codec = "vp9"
        bitrate = "13M"
        minrate = "8M"
        maxrate = "15M"
        audio_bitrate = "192k"
        max_fps = 30
        fps_output = find_fps(fps_rounded, max_fps)
    elif current_platform == "Android H265":
        platform_name = "android"
        codec = "h265"
        bitrate = "13M"
        minrate = "8M"
        maxrate = "15M"
        audio_bitrate = "192k"
        max_fps = 30
        fps_output = find_fps(fps_rounded, max_fps)
    elif current_platform == "Cardboard iOS":
        platform_name = "ios"
        codec = "h264"
        bitrate = "13M"
        minrate = "8M"
        maxrate = "15M"
        audio_bitrate = "192k"
        crf = "21"
        max_fps = 30
        fps_output = find_fps(fps_rounded, max_fps)
    elif current_platform == "High Quality H265":
        platform_name = "HQ"
        codec = "h265"
        bitrate = "75M"
        minrate = "8M"
        maxrate = "15M"
        audio_bitrate = "320k"
        max_fps = 120
        fps_output = find_fps(fps_rounded, max_fps)
    elif current_platform == "YouTube":
        platform_name = "youtube"
        codec = "h264"
        audio_bitrate = "320k"
        max_fps = 60
        fps_output = find_fps(fps_rounded, max_fps)
        crf = "18"
        if (float(fps_output) > 30):
            bitrate = "60M"
            minrate = "53M"
            maxrate = "68M"
        else:
            bitrate = "40M"
            minrate = "35M"
            maxrate = "45M"
    elif current_platform == "Facebook":
        platform_name = "facebook"
        codec = "h264"
        audio_bitrate = "320k"
        max_fps = 60
        if not sequence: fps_output = find_fps(fps_rounded, max_fps)
        if (float(fps_output) > 30):
            bitrate = "60M"
            minrate = "53M"
            maxrate = "68M"
        else:
            bitrate = "40M"
            minrate = "35M"
            maxrate = "45M"
        crf = "18"
    elif current_platform == "Headjack":
        platform_name = "headjack"
        codec = "h265"
        audio_bitrate = "192k"
        max_fps = 60
        if not sequence: fps_output = find_fps(fps_rounded, max_fps)
        if (float(fps_output) > 30):
            bitrate = "44M"
            minrate = "40M"
            maxrate = "50M"
        else:
            bitrate = "22M"
            minrate = "20M"
            maxrate = "30M"
    else:
        codec = "h264"
        platform_name = "etc"

    # Set scaling rules
    if platform_name == "facebook" and aspect_calculated != 2.0:
        vfilter = "crop=h=in_h/2:y=0,"

    if platform_name == "ios":
        print("Cardboard iOS")
        width = "1920"
        height = "1080"
        aspect_ratio = "16:9"

    elif platform_name == "facebook":
        width = "3840"
        height = "1920"
        aspect_ratio = "2:1"

    elif aspect_calculated == 1.0 and int(
            height) >= 4096 and platform_name != "HQ" and platform_name != "headjack" and platform_name != "facebook":  # 1:1
        width = "3840"
        height = "2160"
        aspect_ratio = "16:9"

    elif aspect_calculated == 2.0 and int(
            width) >= 4096 and platform_name != "HQ" and platform_name != "headjack":  # 2:1
        width = "3840"
        height = "1920"
    elif aspect_calculated == 2.0 and int(width) >= 4096 and platform_name == "headjack":
        aspect_ratio = "2:1"
    else:
        aspect_ratio = "16:9"

    # Set output filename

    if right_file is not None:
        left_name, extension = os.path.splitext(os.path.basename(file))
        right_name, extension = os.path.splitext(os.path.basename(right_file))
        name = left_name + '_' + right_name
    else:
        name = ''.join(file.split('.')[:-1])
    name = name + '-' + platform_name + '-' + width + 'x' + height + '-' + fps_output + '-' + codec
    # output = cwd+'/outputs/{}.mp4'.format(name)
    output = os.path.join(output_dir_path, '{}.mp4'.format(name))

    if sequence:
        pattern = '.*?([0-9]+)$'
        file_base = os.path.splitext(file)[0]  # Get filename without extension
        start_number = re.match(pattern, file_base).group(1)
        start_number_length = len(start_number)  # Get number of digits in sequence filenames
        print("RegEx result = ")
        print(start_number)
        print("Length = " + str(start_number_length))
        start_number_cmd = "-start_number"
        # Change input filename
        new_file = file.replace(start_number, "%" + str(start_number_length) + "d")
        print("New file = " + new_file)
    else:
        start_number_cmd = ""
        start_number = ""

    try:
        # Bufsize 2x Maxrate
        # http://superuser.com/questions/945413/how-to-consider-bitrate-maxrate-and-bufsize-of-a-video-for-web
        if right_file is not None:
            filepath = file
        else:
            filepath = os.path.join(input_dir_path, file)
        print("Filepath = " + filepath)

        def status_handler(old, new):
            progress_bar["value"] = new

        # Start progress bar
        runner = FFMpegRunner(filepath, fps_rounded, float(fps_output), sequence)

        if sequence:
            input_file = os.path.join(input_dir_path, new_file)
        else:
            input_file = filepath

        if codec == 'h264':
            print("Codec = h264")
            # Encode 4k stereo mov to 4k H264
            argslist = [
                FFMPEG_PATH,
                '-hide_banner',
                '-y',
                '-v',
                'quiet',
                '-stats',
                '-i', input_file,
                '-r', fps_output,  # Set FPS
                '-c:v', 'libx264',
                '-profile:v', PROFILE,
                '-level', LEVEL,
                '-pix_fmt', 'yuv420p',  # Pixel format / chroma subsampling (422 not supported by baseline profile)
                '-preset', PRESET,
                '-crf', crf,
                '-c:a', 'aac', '-strict', 'experimental', '-b:a', audio_bitrate,
                # Audio settings, must be set to convert mov
                # '-ss', '00:00:00', '-t', '00:00:05',
                output
            ]

            # Insert extra elements into argument list for sequences
            if sequence:
                argslist.insert(6, '-framerate')
                argslist.insert(7, fps_input)

            print("Command: {0}".format(' '.join(argslist)))
            # subprocess.call(argslist)
            runner.run_session(argslist, status_handler=status_handler)

        elif codec == 'h265':
            print("Codec = h265")
            # Encode video to H265
            # Level 3 supported on Android 5.0+ mobile (max 720x480@30)
            # Level 4.1 supported on Android TV (max 1920x1080@30)
            # Level 5.1 necessary for 3840x2160@30 & 4096x2048@30
            argslist = [
                FFMPEG_PATH,
                '-hide_banner',
                '-y',
                '-v',
                'quiet',
                '-stats',
                '-i', input_file,
                '-r', fps_output,  # Set FPS
                '-c:v', 'libx265',
                '-x265-params',
                'log-level=error',
                '-pix_fmt', 'yuv420p',
                '-preset', PRESET,  # '-crf', '23', #CRF_VALUE,
                '-b:v', bitrate,  # Constant bitrate
                # '-maxrate', '20000', '-bufsize', '40000',                   # Limit output bitrate
                # '-x265-params', 'profile=main:level=5.1:frame-threads=4:keyint=1:ref=1:no-open-gop=1:weightp=0:weightb=0:cutree=0:rc-lookahead=0:bframes=0:scenecut=0:b-adapt=0:repeat-headers=1',
                '-c:a', 'aac', '-strict', 'experimental', '-b:a', audio_bitrate,
                # '-ss', '00:00:00', '-t', '00:00:05',
                output]

            # Insert extra elements into argument list for sequences
            if sequence:
                argslist.insert(6, '-framerate')
                argslist.insert(7, fps_input)

            print("Command: {0}".format(' '.join(argslist)))
            runner.run_session(argslist, status_handler=status_handler)

        elif codec == 'vp9':
            print("Codec = vp9")
            # Encode 4k stereo mov to 4k H264
            argslist = [
                FFMPEG_PATH,
                '-hide_banner',
                '-y',
                '-stats',
                '-i', input_file,
                '-threads', '16',
                # Set output resolution
                '-r', fps_output,
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuv420p',  # Pixel format / chroma subsampling (422 not supported by baseline profile)
                # '-crf', crf,
                # '-minrate', minrate, '-maxrate', maxrate,
                '-b:v', bitrate,  # Limit bitrate on 15Mbit
                '-c:a', 'libvorbis', '-b:a', audio_bitrate,  # Audio settings, must be set to convert mov
                # '-ss', '00:00:00', '-t', '00:00:05',
                       output[:-3] + 'webm'
            ]

            # Insert extra elements into argument list for sequences
            if sequence:
                argslist.insert(6, '-framerate')
                argslist.insert(7, fps_input)

            # Insert extra arguments for stereoscopic
            if right_file is not None:
                map_x_file = 'maps/l0000_x.pgm'
                map_y_file = 'maps/l0000_y.pgm'
                argslist.insert(8, '-i')
                argslist.insert(9, right_file)
                argslist.insert(10, '-i')
                argslist.insert(11, map_x_file)
                argslist.insert(12, '-i')
                argslist.insert(13, map_y_file)
                argslist.insert(14, '-filter_complex')
                argslist.insert(
                    15,
                    '[0:v][2][3]remap[left];[1:v][2][3]remap[right];'
                    '[left][right]vstack[stacked];'
                    '[stacked]' + vfilter + 'scale=w=' + width + ':h=-1:flags=lanczos[out]')
                argslist.insert(16, '-map')
                argslist.insert(17, '[out]')
            else:
                argslist.insert(8, '-vf')
                argslist.insert(9, vfilter + 'scale=' + width + 'x' + height + ',setdar=' + aspect_ratio)
            print("Command: {0}".format(' '.join(argslist)))
            # subprocess.call(argslist)
            runner.run_session(argslist, status_handler=status_handler)

        else:
            print("Invalid codec selected: " + CODEC)

    finally:
        print(output + " encode ready!")


# -------------------------------------------------------------------------------
# GUI
# -------------------------------------------------------------------------------

# bgcolor = "#2F4050"
# Create root window object
root = Tk()
# root.configure(background = bgcolor)
root.title("VRencoder")

# Set icon
# logo = PhotoImage(file='logo.gif')
# root.tk.call('wm', 'iconphoto', root._w, logo)
# root.tk.call('wm', 'iconbitmap', root._w, '-default', 'icon.ico') >> original
# root.tk.call('wm', 'iconbitmap', root._w, 'icon.ico')
root.tk.call('wm', 'iconbitmap', root._w)

# Create list of platforms
platforms = [
    'Desktop VR',
    'Android H265',
    'Android VP9',
    'Cardboard iOS',
    'High Quality H265',
    'YouTube',
    'Facebook'
]
selected_platforms = []

# Loop through list of platforms, display them in the GUI, and store values in variable
for x in range(len(platforms)):
    var = IntVar()
    list = Checkbutton(root, text=platforms[x], variable=var)
    print("list = Checkbutton(root, text=" + str(platforms[x]) + ", variable=" + str(var))
    selected_platforms.append([platforms[x], var])
    list.grid(row=(x + 6), column=1, padx=5, pady=5, sticky=W)

print(selected_platforms)

ftypes = [
    ('Mp4 files', ('*.mp4', '*.MP4')),
    ('Mov files', '*.mov;*.MOV'),
    ('Avi files', '*.avi;*.AVI'),
    ('Wmv files', '*.wmv;*.WMV'),
    ('Mpeg files', '*.mpg;*.mpeg;*.m2ts;*.MPG;*MPEG;*.M2T'),
    ('All files', '*'),
]


def askinputdir():
    global input_dir
    global input_dir_path
    directory = tkFileDialog.askdirectory()
    if directory:
        input_dir_path = directory
        input_dir.set(directory)


def askleftfile():
    global input_filename_left
    global input_file_left
    file = tkFileDialog.askopenfilename(filetypes=ftypes)
    if file:
        input_file_left = file
        input_filename_left.set(file)


def askrightfile():
    global input_filename_right
    global input_file_right
    file = tkFileDialog.askopenfilename(filetypes=ftypes)
    if file:
        input_file_right = file
        input_filename_right.set(file)


def askoutputdir():
    global output_dir
    global output_dir_path
    directory = tkFileDialog.askdirectory()
    if directory:
        output_dir_path = directory
        output_dir.set(directory)


# input_dir = StringVar()
# inputButton = Button(root, text="Choose input directory", width=20, command=askinputdir)
# inputButton.grid(row=1, column=1, padx=5, pady=5, sticky=E)
# Entry(root,
#       state="readonly",
#       width=40,
#       textvariable=input_dir).grid(row=1, column=2, padx=5, pady=5)

input_filename_left = StringVar(root, value="/home/sdc/dev/test-files/left.MP4")
inputRightButton = Button(root, text="Choose left file", width=20, command=askleftfile)
inputRightButton.grid(row=1, column=1, padx=5, pady=5, sticky=E)
Entry(root,
      state="readonly",
      width=40,
      textvariable=input_filename_left).grid(row=1, column=2, padx=5, pady=5)

input_filename_right = StringVar(root, value="/home/sdc/dev/test-files/right.MP4")
inputRightButton = Button(root, text="Choose right file", width=20, command=askrightfile)
inputRightButton.grid(row=2, column=1, padx=5, pady=5, sticky=E)
Entry(root,
      state="readonly",
      width=40,
      textvariable=input_filename_right).grid(row=2, column=2, padx=5, pady=5)

output_dir = StringVar()
outputButton = Button(root, text="Choose output directory", width=20, command=askoutputdir)
outputButton.grid(row=3, column=1, padx=5, pady=5, sticky=E)
Entry(root,
      state="readonly",
      width=40,
      textvariable=output_dir).grid(row=3, column=2, padx=5, pady=5)

global progress_bar
progress_bar = Progressbar(root, orient='horizontal', mode='determinate')
progress_bar.grid(row=16, columnspan=3, padx=5, pady=5, sticky=W + E)
progress_bar["value"] = 0
progress_bar["maximum"] = 100

# Create and display encoding button
encode_button = Button(root, text="Start encoding!", command=start_thread)
encode_button.grid(row=17, column=1, padx=5, pady=5, sticky=W)

time_remaining_label = Label(root, text="")
time_remaining_label.grid(row=17, column=2, padx=5, pady=5, sticky=E)
global status_bar
status_bar = StatusBar(root)
status_bar.grid(row=18, columnspan=3, sticky="nsew")
root.grid_columnconfigure(1, weight=1)
root.grid_rowconfigure(18, weight=1)


root.mainloop()
