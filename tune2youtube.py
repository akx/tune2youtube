# -- encoding: utf-8 --
"""
Turns audio files (whatever you can throw at ffmpeg)
into video files with a cover image.
"""
from __future__ import with_statement, print_function
import argparse
import json
import os
import subprocess
import sys

NEED_SHELL = (sys.platform == "win32")
FFMPEG_PATH = os.environ.get("FFMPEG_PATH") or ""
if FFMPEG_PATH:
    FFMPEG_PATH += os.sep


def probe_file(filename):
    """
    Probe a file for stream information using ffprobe.

    :param filename: The filename to probe
    :return: A dict of stream information
    :rtype: dict
    """
    probe_text, _ = subprocess.Popen(
        [
            "%sffprobe" % FFMPEG_PATH,
            "-print_format", "json",
            "-show_streams",
            filename
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # Not that we'll read it...
        shell=NEED_SHELL
    ).communicate()
    return json.loads(probe_text)


def scaling_round(val, factor=16, max_value=0):
    """
    Round the given value to the nearest multiple of `factor`.

    If the optional `max_value` is given, the nearest multiple
    not above that `max_value` is returned.

    :param val: The value to round.
    :param factor: Rounding multiple.
    :param max_value: Maximum return value.
    :return: Rounded int
    :rtype: int
    """
    vsc = int(val / factor)
    vmin = vsc * factor
    vmax = (vsc + 1) * factor
    if (max_value and vmax > max_value) or abs(val - vmin) < abs(val - vmax):
        return vmin
    return vmax


def get_cover_filter_string(cover_filename, video_width, video_height):
    """
    Figure out a letterbox/pillbox filter string for the cover image.

    :param cover_filename: The image file to use.
    :param video_width: The result video width.
    :param video_height: The result video height.
    :return: ffmpeg filter string
    :rtype: str
    """

    # Thanks to http://superuser.com/a/547406 for ideas.

    cover_stream_info = probe_file(cover_filename)["streams"][0]
    cover_width = float(cover_stream_info["width"])
    cover_height = float(cover_stream_info["height"])
    cover_aspect = cover_width / cover_height
    video_aspect = float(video_width) / float(video_height)
    if cover_width >= cover_height and cover_aspect > video_aspect:
        image_width = video_width
        image_height = image_width / cover_aspect
    else:
        image_height = video_height
        image_width = image_height * cover_aspect
    assert image_height <= video_height
    assert image_width <= video_width
    image_width = scaling_round(image_width)
    image_height = scaling_round(image_height)

    scale_filter = "scale=%d:%d" % (image_width, image_height)
    pad_filter = "pad=%d:%d:%d:%d" % (
        video_width, video_height,
        (video_width - image_width) / 2, (video_height - image_height) / 2
    )
    return "%s,%s" % (scale_filter, pad_filter)


def process(cover_path, audio_path, output_path=None, width=1280, height=720):
    """
    Process the given files into a cute video.

    :param cover_path: Cover image path
    :param audio_path: Audio file path
    :param output_path: Output path. Optional.
    :param width: Result video width
    :param height: Result video height
    :return: The output path
    :rtype: str
    """
    if not output_path:
        audio_basename = os.path.splitext(os.path.basename(audio_path))[0]
        output_path = "%s.mp4" % audio_basename

    filter_string = get_cover_filter_string(cover_path, width, height)

    ffmpeg_args = [
        "%sffmpeg" % FFMPEG_PATH,
        "-loop", "1",
        "-i", cover_path,
        "-i", audio_path,
        "-r:v", "10",  # Could probably be lower
        "-s:v", "%dx%d" % (width, height),
        "-c:v", "libx264",
        "-crf:v", "22",
        "-filter:v", filter_string,
        "-pix_fmt", "yuv420p",
    ]

    needs_transcode = not audio_path.endswith(".mp3")

    if needs_transcode:
        ffmpeg_args.extend([
            "-c:a", "aac",
            "-strict", "experimental",
            "-b:a", "320k"
        ])
    else:
        ffmpeg_args.extend([
            "-c:a", "copy",
        ])
    ffmpeg_args.extend([
        "-shortest",
        output_path
    ])
    subprocess.check_call(ffmpeg_args, shell=NEED_SHELL)
    return output_path


def unwrap_args(args_ns):
    """
    "Unwrap" the given `argparse` namespace into a dict.

    :type args_ns: argparse.Namespace
    :rtype: dict
    """
    args_dict = {}
    for key, value in vars(args_ns).items():
        if isinstance(value, list):
            value = value[0]
        args_dict[key] = value
    return args_dict


def command_line():
    """
    Process things from the command line.
    """
    parser = argparse.ArgumentParser(
        description="Convert audio files to videos with a cover image.",
        add_help=False  # conflicts with `-h`
    )
    parser.add_argument("--help", action='help', default=argparse.SUPPRESS)
    parser.add_argument(
        "-c", "-i", nargs=1, required=True, dest="cover_path",
        help="Cover image file", metavar="FILE"
    )
    parser.add_argument(
        "-s", "-a", nargs=1, required=True, dest="audio_path",
        help="Song file", metavar="FILE"
    )
    parser.add_argument(
        "-o", nargs="?", default=None, dest="output_path",
        help="Output filename (optional)", metavar="FILE"
    )
    parser.add_argument(
        "-w", type=int, default=1280, nargs="?", dest="width",
        help="Video width", metavar="PX"
    )
    parser.add_argument(
        "-h", type=int, default=720, nargs="?", dest="height",
        help="Video height", metavar="PX"
    )
    args = parser.parse_args()
    output_path = process(**unwrap_args(args))
    print("OK:", output_path)


if __name__ == "__main__":
    command_line()
