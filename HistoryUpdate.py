#!/usr/bin/python3

import PIL.Image
import sys, io, os
import datetime
import asyncio
import aiohttp
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess  # To run ffmpeg

USER_AGENT = "ppfun historyDownload 1.0 " + ' '.join(sys.argv[1:])
PPFUN_URL = "https://pixelplanet.fun"
PPFUN_STORAGE_URL = "https://storage.pixelplanet.fun"

# how many frames to skip
#  1 means none
#  2 means that every second frame gets captured
#  3 means every third
#  [...]
frameskip = 1

async def fetchMe():
    url = f"{PPFUN_URL}/api/me"
    headers = {
      'User-Agent': USER_AGENT
    }
    async with aiohttp.ClientSession() as session:
        attempts = 0
        while True:
            try:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    return data
            except:
                if attempts > 3:
                    print(f"Could not get {url} in three tries, cancelling")
                    raise
                attempts += 1
                print(f"Failed to load {url}, trying again in 5s")
                await asyncio.sleep(5)
                pass

async def fetch(session, url, offx, offy, image, bkg, needed = False):
    attempts = 0
    headers = {
      'User-Agent': USER_AGENT
    }
    while True:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    if needed:
                        img = PIL.Image.new('RGB', (256, 256), color=bkg)
                        image.paste(img, (offx, offy))
                        img.close()
                    return
                if resp.status != 200:
                    if needed:
                        continue
                    return
                data = await resp.read()
                img = PIL.Image.open(io.BytesIO(data)).convert('RGBA')
                image.paste(img, (offx, offy), img)
                img.close()
                return
        except:
            if attempts > 3:
                raise
            attempts += 1
            pass

async def get_area(canvas_id, canvas, x, y, w, h, start_date, end_date, output_folder):
    canvas_size = canvas["size"]
    bkg = tuple(canvas['colors'][0])

    delta = datetime.timedelta(days=1)
    end_date = end_date.strftime("%Y%m%d")
    iter_date = None
    cnt = 0
    previous_day = PIL.Image.new('RGB', (w, h), color=bkg)
    while iter_date != end_date:
        iter_date = start_date.strftime("%Y%m%d")
        print('------------------------------------------------')
        print(f'Getting frames for date {iter_date}')
        start_date = start_date + delta

        fetch_canvas_size = canvas_size
        if 'historicalSizes' in canvas:
            for ts in canvas['historicalSizes']:
                date = ts[0]
                size = ts[1]
                if iter_date <= date:
                    fetch_canvas_size = size

        offset = int(-fetch_canvas_size / 2)
        xc = (x - offset) // 256
        wc = (x + w - offset) // 256
        yc = (y - offset) // 256
        hc = (y + h - offset) // 256
        print(f"Load from {xc} / {yc} to {wc + 1} / {hc + 1} with canvas size {fetch_canvas_size}")

        tasks = []
        async with aiohttp.ClientSession() as session:
            image = PIL.Image.new('RGBA', (w, h))
            for iy in range(yc, hc + 1):
                for ix in range(xc, wc + 1):
                    url = f'{PPFUN_STORAGE_URL}/{iter_date[0:4]}/{iter_date[4:6]}/{iter_date[6:]}/{canvas_id}/tiles/{ix}/{iy}.png'
                    offx = ix * 256 + offset - x
                    offy = iy * 256 + offset - y
                    tasks.append(fetch(session, url, offx, offy, image, bkg, True))
            await asyncio.gather(*tasks)
            print('Got start of day')

            clr = image.getcolors(1)
            if clr is not None:
                print("Got faulty full-backup frame, using last frame from previous day instead.")
                image = previous_day.copy()
            cnt += 1
            image.save(f'./timelapse/t{cnt}.png')

            headers = {
                'User-Agent': USER_AGENT
            }
            while True:
                async with session.get(f'{PPFUN_URL}/history?day={iter_date}&id={canvas_id}', headers=headers) as resp:
                    try:
                        time_list = await resp.json()
                        break
                    except:
                        print(f"Couldn't decode json for day {iter_date}, trying again")

            i = 0
            for time in time_list:
                i += 1
                if (i % frameskip) != 0:
                    continue
                if time == '0000':
                    continue
                tasks = []
                image_rel = image.copy()
                for iy in range(yc, hc + 1):
                    for ix in range(xc, wc + 1):
                        url = f'{PPFUN_STORAGE_URL}/{iter_date[0:4]}/{iter_date[4:6]}/{iter_date[6:]}/{canvas_id}/{time}/{ix}/{iy}.png'
                        offx = ix * 256 + offset - x
                        offy = iy * 256 + offset - y
                        tasks.append(fetch(session, url, offx, offy, image_rel, bkg))
                await asyncio.gather(*tasks)
                print(f'Got time {time}')
                cnt += 1
                image_rel.save(f'./timelapse/t{cnt}.png')
                if time == time_list[-1]:
                    print("Remembering last frame of day.")
                    previous_day.close()
                    previous_day = image_rel.copy()
                image_rel.close()
            image.close()
    previous_day.close()


async def fetchMe():
    url = f"{PPFUN_URL}/api/me"
    headers = {'User-Agent': USER_AGENT}
    async with aiohttp.ClientSession() as session:
        attempts = 0
        while True:
            try:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    return data
            except:
                if attempts > 3:
                    print(f"Could not get {url} in three tries, cancelling")
                    raise
                attempts += 1
                print(f"Failed to load {url}, trying again in 5s")
                await asyncio.sleep(5)
                pass


class TimelapseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PixelPlanet Timelapse Downloader")
        
        
        self.show_warning()

        self.create_widgets()

    def show_warning(self):
        
        messagebox.showinfo(
            "Warning",
            "This program is not affiliated by PixelPlanet.fun moderators/developers. This program only used to download templates from the website."
        )

    def create_widgets(self):
        tk.Label(self.root, text="Canvas ID:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.canvas_id_entry = tk.Entry(self.root, width=30)
        self.canvas_id_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(self.root, text="Start Coordinates (x_y):").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.start_coords_entry = tk.Entry(self.root, width=30)
        self.start_coords_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(self.root, text="End Coordinates (x_y):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.end_coords_entry = tk.Entry(self.root, width=30)
        self.end_coords_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(self.root, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.start_date_entry = tk.Entry(self.root, width=30)
        self.start_date_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(self.root, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.end_date_entry = tk.Entry(self.root, width=30)
        self.end_date_entry.grid(row=4, column=1, padx=10, pady=5)

        tk.Label(self.root, text="Output Folder:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
        self.output_folder_label = tk.Label(self.root, text="Select Folder", relief="sunken", width=30)
        self.output_folder_label.grid(row=5, column=1, padx=10, pady=5)
        self.output_folder_button = tk.Button(self.root, text="Browse", command=self.select_output_folder)
        self.output_folder_button.grid(row=5, column=2, padx=10, pady=5)

        tk.Label(self.root, text="Output Video Filename (without extension):").grid(row=6, column=0, padx=10, pady=5, sticky="e")
        self.video_filename_entry = tk.Entry(self.root, width=30)
        self.video_filename_entry.grid(row=6, column=1, padx=10, pady=5)

        self.start_button = tk.Button(self.root, text="Start Download", command=self.start_download)
        self.start_button.grid(row=7, column=0, columnspan=3, pady=20)

        self.status_label = tk.Label(self.root, text="Status: Ready", width=50)
        self.status_label.grid(row=8, column=0, columnspan=3, pady=5)

        self.progress = ttk.Progressbar(self.root, length=300, mode="indeterminate")
        self.progress.grid(row=9, column=0, columnspan=3, pady=5)

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_label.config(text=folder)

    def start_download(self):
        canvas_id = self.canvas_id_entry.get()
        start_coords = self.start_coords_entry.get()
        end_coords = self.end_coords_entry.get()
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        output_folder = self.output_folder_label.cget("text")
        video_filename = self.video_filename_entry.get()

        if not canvas_id or not start_coords or not end_coords or not start_date or not video_filename or not output_folder:
            messagebox.showerror("Input Error", "All fields must be filled in.")
            return

        try:
            start_date = datetime.date.fromisoformat(start_date)
            end_date = datetime.date.fromisoformat(end_date)
        except ValueError:
            messagebox.showerror("Date Error", "Invalid date format. Use YYYY-MM-DD.")
            return

        if not os.path.exists(output_folder):
            messagebox.showerror("Output Folder Error", "The selected output folder does not exist.")
            return

        self.disable_ui()

        asyncio.run(self.download_timelapse(canvas_id, start_coords, end_coords, start_date, end_date, output_folder, video_filename))

    def disable_ui(self):
        self.canvas_id_entry.config(state="disabled")
        self.start_coords_entry.config(state="disabled")
        self.end_coords_entry.config(state="disabled")
        self.start_date_entry.config(state="disabled")
        self.end_date_entry.config(state="disabled")
        self.output_folder_button.config(state="disabled")
        self.video_filename_entry.config(state="disabled")
        self.start_button.config(state="disabled")
        self.progress.grid(row=9, column=0, columnspan=3, pady=5)
        self.progress.start()

    def enable_ui(self):
        self.canvas_id_entry.config(state="normal")
        self.start_coords_entry.config(state="normal")
        self.end_coords_entry.config(state="normal")
        self.start_date_entry.config(state="normal")
        self.end_date_entry.config(state="normal")
        self.output_folder_button.config(state="normal")
        self.video_filename_entry.config(state="normal")
        self.start_button.config(state="normal")
        self.progress.stop()

    async def download_timelapse(self, canvas_id, start_coords, end_coords, start_date, end_date, output_folder, video_filename):
        apime = await fetchMe()

        if canvas_id not in apime['canvases']:
            messagebox.showerror("Invalid Canvas", "The selected canvas ID is invalid.")
            self.enable_ui()
            return

        canvas = apime['canvases'][canvas_id]

        if 'v' in canvas and canvas['v']:
            messagebox.showerror("Error", "Can't get area for 3D canvas.")
            self.enable_ui()
            return

        start = start_coords.split('_')
        end = end_coords.split('_')
        x = int(start[0])
        y = int(start[1])
        w = int(end[0]) - x + 1
        h = int(end[1]) - y + 1

        if not os.path.exists('./timelapse'):
            os.mkdir('./timelapse')

        await get_area(canvas_id, canvas, x, y, w, h, start_date, end_date, output_folder)

        # Run ffmpeg to create video
        output_video_path = os.path.join(output_folder, f"{video_filename}.webm")
        ffmpeg_command = [
            'ffmpeg', '-framerate', '15', '-f', 'image2', 
            '-i', './timelapse/t%d.png', '-c:v', 'libvpx-vp9', 
            '-pix_fmt', 'yuva420p', output_video_path
        ]
        
        try:
            subprocess.run(ffmpeg_command, check=True)
            messagebox.showinfo("Success", f"Timelapse video created successfully: {output_video_path}")
        except subprocess.CalledProcessError:
            messagebox.showerror("FFmpeg Error", "There was an error creating the video.")
        
        self.enable_ui()

if __name__ == "__main__":
    root = tk.Tk()
    app = TimelapseApp(root)
    root.mainloop()
