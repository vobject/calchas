#!/usr/bin/env python3

import argparse
import csv
import datetime
import json
import logging
import os
import platform
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

# stream_handler = logging.StreamHandler()
# stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
# logger = logging.getLogger("laocoön")
# logger.addHandler(stream_handler)
# logging = logger
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

import fabric
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import streamlit as st

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, "src")))

from calchas import trip


def to_datetime(timestamp):
    # workaround for timestamp format change
    timestamp = float(timestamp)/1000. if float(timestamp) > 1000000000000 else timestamp
    return datetime.datetime.fromtimestamp(float(timestamp))


def run(trip_path: str):
    with trip.TripManager.read(trip_path) as t:
        st.sidebar.text(t.directory)
        st.sidebar.text(json.dumps(t.options, indent=4))

        # SYSTEMINFO
        csv_path = os.path.join(trip_path, "systeminfo.csv")
        if os.path.isfile(csv_path):
            df = pd.read_csv(csv_path, index_col="timestamp", converters={"timestamp": to_datetime})

            system_infos = ["system_cpu_percent", "system_virtual_memory_percent", "disk_percent",]
            system_cpu_times = ["system_cpu_times_percent_system", "system_cpu_times_percent_user", "system_cpu_times_percent_idle",]
            process_infos = ["process_cpu_percent", "process_mem_rss_percent", "process_mem_vms_percent",]
            st.markdown("## SYSTEMINFO")
            for x in [system_infos, system_cpu_times, process_infos]:
                # st.write(x)
                # fig, ax = plt.subplots()
                # df[x].plot(ax=ax)
                # ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=list(range(0, 60, 5))))
                # ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                # ax.set_xlabel("Time")
                # ax.set_ylabel("Percent")
                # st.write(fig)
                st.line_chart(df[x])

            system_load = ["system_loadavg_1", "system_loadavg_5", "system_loadavg_15",]
            process_cpu_times = ["process_cpu_time_system", "process_cpu_time_user",]
            temps = ["system_cpu_temp", "cpu_temp",]
            temps = ["system_cpu_temp",]
            for x in [system_load, process_cpu_times, temps]:
                # st.write(x)
                # fig, ax = plt.subplots()
                # df[x].plot(ax=ax)
                # ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=list(range(0, 60, 5))))
                # ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                # ax.set_xlabel("Time")
                # st.write(fig)
                st.line_chart(df[x])

        # IMU
        csv_path = os.path.join(trip_path, "imu.csv")
        if os.path.isfile(csv_path):
            df = pd.read_csv(csv_path, index_col="timestamp", converters={"timestamp": to_datetime})

            gyro = ["gyro_x", "gyro_y", "gyro_z",]
            acc = ["acc_x", "acc_y", "acc_z",]
            rot = ["rot_x", "rot_y",]

            st.markdown("## IMU")
            for x in [gyro, acc, rot]:
                # st.write(x)
                # fig, ax = plt.subplots()
                # df[x].plot(linewidth=0.3, ax=ax)
                # ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=list(range(0, 60, 5))))
                # ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                # ax.set_xlabel("Time")
                # ax.set_ylabel("Percent")
                # st.write(fig)
                st.line_chart(df[x])

        # GPS
        csv_path = os.path.join(trip_path, "gps.csv")
        if os.path.isfile(csv_path):
            try:
                df = pd.read_csv(csv_path, index_col="timestamp", converters={"timestamp": to_datetime})
                df = df.replace(0, np.nan)
                df = df.dropna(how='all', axis=0)

                # with open(csv_path) as f:
                #     r = csv.DictReader(f, delimiter=",")
                #     for entry in r:
                #         lon = entry["longitude"]
                #         lat = entry["latitude"]
                #         alt = entry["altitude"]
                #         if lon in ("", "0.0", "0"): continue
                #         if lat in ("", "0.0", "0"): continue
                #         if alt in ("", "0.0", "0"): continue
                #         kml_pos_list.append(f"{lon},{lat},{alt}")

                st.markdown("## GPS")
                st.dataframe(df)
                st.write(len(df))
                st.map(df)
            except pd.errors.EmptyDataError:
                logging.warning("Empty GPS file.")

        # PICAM
        mp4_path = os.path.join(trip_path, "picam.mp4")
        if os.path.isfile(mp4_path):
            st.markdown("## PICAM")

            cam = cv2.VideoCapture(mp4_path)
            ret_val, img = cam.read()
            cam.release()
            if ret_val:
                st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), use_column_width=True)

            # st.video(open(mp4_path, 'rb'))
            # video_file = open(mp4_path, 'rb')
            # video_bytes = video_file.read(1024*1024*64)
            # st.video(video_bytes)
            # st.video("https://www.youtube.com/watch?v=rq5FReMzBFc")

        # progress_bar = st.sidebar.progress(0)
        # status_text = st.sidebar.empty()
        # last_rows = np.random.randn(1, 1)
        # chart = st.line_chart(last_rows)

        # for i in range(1, 101):
        #     new_rows = last_rows[-1, :] + np.random.randn(5, 1).cumsum(axis=0)
        #     status_text.text("%i%% Complete" % i)
        #     chart.add_rows(new_rows)
        #     progress_bar.progress(i)
        #     last_rows = new_rows
        #     time.sleep(0.05)

        # progress_bar.empty()

        # # Streamlit widgets automatically run the script from top to bottom. Since
        # # this button is not connected to any other logic, it just causes a plain
        # # rerun.
        # st.button("Re-run")


def get_remote_trip_dirs(hostname: str, trips_dir: str):
    logging.info("get_remote_trip_dirs()")
    with fabric.Connection(hostname) as conn:
        result = conn.run(f"ls -d {trips_dir}/*", hide=True)
        dirs_list = result.stdout.strip().split("\n")
        return [name for name in dirs_list if trip.TripManager.is_trip_name(name)]


def import_remote_trips(hostname: str, trip_dirs: List[str], out_dir: str, progress_bar):
    logging.info("import_remote_trips()")
    with fabric.Connection(hostname) as conn:
        progress_bar.progress(0)
        for i, remote_trip_dir in enumerate(trip_dirs):
            logging.info(f"Importing {remote_trip_dir}")
            result = conn.run(f"ls {remote_trip_dir}", hide=True)
            trip_files = result.stdout.strip().split("\n")

            local_trip_dir = os.path.join(out_dir, os.path.basename(remote_trip_dir))
            os.makedirs(local_trip_dir, exist_ok=True)

            for trip_file in trip_files:
                logging.info(f"Copy {remote_trip_dir}/{trip_file}")
                conn.get(
                    f"{remote_trip_dir}/{trip_file}",
                    os.path.join(local_trip_dir, trip_file),
                )

            # TODO: Improve me!
            picam_h264_path = os.path.join(local_trip_dir, "picam.h264")
            if os.path.isfile(picam_h264_path):
                mp4_path = f"{picam_h264_path[:-4]}mp4"
                ffmpeg_path = r"C:\Users\vobject\Tools\ffmpeg-4.2.1-win64-static\bin\ffmpeg.exe"
                # ffmpeg_path = r"C:\Users\user\Downloads\Python\ffmpeg-20200417-889ad93-win64-static\bin\ffmpeg.exe"
                cmd = f"{ffmpeg_path} -framerate 10 -i {picam_h264_path} -c copy {mp4_path} -y"
                logging.info(cmd)
                subprocess.run(cmd)

            progress_bar.progress(1. / len(trip_dirs) * (i + 1))


def clear_remote_trips(hostname: str, trip_dirs: List[str], progress_bar):
    logging.info("clear_remote_trips()")
    with fabric.Connection(hostname) as conn:
        progress_bar.progress(0)
        for i, remote_trip_dir in enumerate(trip_dirs):
            logging.info(f"Remove {remote_trip_dir}")
            conn.run(f"rm -rf {remote_trip_dir}", hide=True)
            progress_bar.progress(1. / len(trip_dirs) * (i + 1))


def run_import(args):
    if args.remote:
        hostname, remote_trips_dir = args.remote.split(":")
    else:
        hostname, remote_trips_dir = "pi@zpi", "~/git/calchas-git"

    trip_dirs = get_remote_trip_dirs(hostname, remote_trips_dir)

    for td in trip_dirs:
        st.write(td)

    progress_bar = st.progress(0)
    if st.button(f"Import"):
        import_remote_trips(hostname, trip_dirs, args.trips, progress_bar)
    if st.button(f"Clear"):
        clear_remote_trips(hostname, trip_dirs, progress_bar)


def run_local(args):
    trip_dirs = trip.TripManager.list(args.trips)
    trip_name = st.sidebar.selectbox("Choose a trip", ["-"] + [os.path.basename(td) for td in trip_dirs], 0)

    if trip_name == "-":
        st.write("# Choose a trip")
        for td in trip_dirs:
            st.write(td)
        st.sidebar.success("Select a trip above.")

        # st.write(os.getcwd())
        # mp4_path = r"download.mp4"
        # # video_file = open(mp4_path, 'rb')
        # # video_bytes = video_file.read()
        # st.video(open(mp4_path, 'rb'))
        # st.video("https://www.youtube.com/watch?v=rq5FReMzBFc")
    else:
        run(os.path.join(args.trips, trip_name))


def parse_args():
    parser = argparse.ArgumentParser(description="Manage Calchas trips")
    parser.add_argument("-d", "--trips", type=str, default=".", help="The trips directory")
    parser.add_argument("-r", "--remote", type=str, default=None, help="The trips directory on the remote device (e.g. 'zpi:/home/pi/calchas-out')")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Print diagnostic messages")

    args = parser.parse_args()
    if args.verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARN)

    return args


def main():
    logging.info("!!!MAIN_RUNNING!!!")
    args = parse_args()
    os.makedirs(args.trips, exist_ok=True)

    # if args.remote:
    #     run_import(args)
    # else:
    #     run_local(args)

    if args.remote:
        mode = st.sidebar.radio("Mode", ["Analyze", "Import"], index=0)
        if mode == "Analyze":
            run_local(args)
        elif mode == "Import":
            run_import(args)
    else:
        run_local(args)


if __name__ == "__main__":
    main()


# import pdb;pdb.set_trace()

# Import mode: streamlit run src/laocoön.py -- --trips=".." --remote=pi@zpi:~/git/calchas-git -v
# Analyse mode: streamlit run src/laocoön.py -- --trips=".." -v
