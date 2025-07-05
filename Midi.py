import os
import time
from threading import Thread
from tkinter import Tk, Button, filedialog, Label, Canvas, Frame
from mido import MidiFile
from pynput.keyboard import Controller, Key, Listener as KeyboardListener

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
KEYBOARD_MAPPING = {
    "C2": ("1", False), "C#2": ("1", True), "D2": ("2", False), "D#2": ("2", True), "E2": ("3", False),
    "F2": ("4", False), "F#2": ("4", True), "G2": ("5", False), "G#2": ("5", True), "A2": ("6", False),
    "A#2": ("6", True), "B2": ("7", False), "C3": ("8", False), "C#3": ("8", True), "D3": ("9", False),
    "D#3": ("9", True), "E3": ("0", False), "F3": ("q", False), "F#3": ("q", True), "G3": ("w", False),
    "G#3": ("w", True), "A3": ("e", False), "A#3": ("e", True), "B3": ("r", False), "C4": ("t", False),
    "C#4": ("t", True), "D4": ("y", False), "D#4": ("y", True), "E4": ("u", False), "F4": ("i", False),
    "F#4": ("i", True), "G4": ("o", False), "G#4": ("o", True), "A4": ("p", False), "A#4": ("p", True),
    "B4": ("a", False), "C5": ("s", False), "C#5": ("s", True), "D5": ("d", False), "D#5": ("d", True),
    "E5": ("f", False), "F5": ("g", False), "F#5": ("g", True), "G5": ("h", False), "G#5": ("h", True),
    "A5": ("j", False), "A#5": ("j", True), "B5": ("k", False), "C6": ("l", False), "C#6": ("l", True),
    "D6": ("z", False), "D#6": ("z", True), "E6": ("x", False), "F6": ("c", False), "F#6": ("c", True),
    "G6": ("v", False), "G#6": ("v", True), "A6": ("b", False), "A#6": ("b", True), "B6": ("n", False),
    "C7": ("m", False)
}

keyboard = Controller()
events = []
is_playing = False
limit_to_61_keys = True
use_velocity = True
play_thread = None

def midi_note_to_key(note_number):
    octave = (note_number // 12) - 1
    note = NOTE_NAMES[note_number % 12]
    return KEYBOARD_MAPPING.get(f"{note}{octave}")

def normalize_to_61_keys(note, min_note=36, max_note=96):
    while note < min_note:
        note += 12
    while note > max_note:
        note -= 12
    return note

def parse_midi(path):
    midi = MidiFile(path)
    time_acc = 0
    out = []
    for msg in midi:
        time_acc += msg.time
        if msg.type in ['note_on', 'note_off']:
            event_type = 'note_off' if msg.velocity == 0 or msg.type == 'note_off' else 'note_on'
            note = normalize_to_61_keys(msg.note) if limit_to_61_keys else msg.note
            velocity = msg.velocity if event_type == 'note_on' else 0
            out.append((time_acc, event_type, note, velocity))
    return out

def playback(events):
    global is_playing
    start_time = time.perf_counter()
    is_playing = True
    events.sort(key=lambda e: e[0])
    key_press_counts = {}
    i = 0
    n = len(events)

    while i < n and is_playing:
        now = time.perf_counter() - start_time
        current_time = events[i][0]
        wait_time = current_time - now
        if wait_time > 0.005:
            time.sleep(wait_time - 0.002)
        while time.perf_counter() - start_time < current_time:
            pass

        while i < n and abs(events[i][0] - current_time) < 1e-6:
            etime, etype, note, velocity = events[i]
            i += 1
            key_info = midi_note_to_key(note)
            if not key_info:
                continue
            key_char, shift = key_info
            key_id = (key_char, shift)

            if etype == 'note_on':
                count = key_press_counts.get(key_id, 0)
                if count == 0:
                    if shift:
                        keyboard.press(Key.shift)
                    keyboard.press(key_char)
                    if shift:
                        keyboard.release(Key.shift)
                key_press_counts[key_id] = count + 1

                if use_velocity:
                    duration = max(0.02, min(0.1, (velocity / 127) * 0.1))
                    def delayed_release(kid, delay):
                        time.sleep(delay)
                        if kid in key_press_counts:
                            key_press_counts[kid] -= 1
                            if key_press_counts[kid] <= 0:
                                del key_press_counts[kid]
                                kchar, kshift = kid
                                if kshift:
                                    keyboard.press(Key.shift)
                                keyboard.release(kchar)
                                if kshift:
                                    keyboard.release(Key.shift)
                    Thread(target=delayed_release, args=(key_id, duration), daemon=True).start()

            elif etype == 'note_off' and not use_velocity:
                if key_id in key_press_counts:
                    key_press_counts[key_id] -= 1
                    if key_press_counts[key_id] <= 0:
                        del key_press_counts[key_id]
                        if shift:
                            keyboard.press(Key.shift)
                        keyboard.release(key_char)
                        if shift:
                            keyboard.release(Key.shift)

    for key_id in list(key_press_counts.keys()):
        key_char, shift = key_id
        if shift:
            keyboard.press(Key.shift)
        keyboard.release(key_char)
        if shift:
            keyboard.release(Key.shift)

def play_midi_file(path):
    global events
    events = parse_midi(path)
    playback(events)

def start_play():
    global is_playing, play_thread
    if not midi_path_label['text']:
        status_label.config(text="No MIDI file loaded.")
        return
    if is_playing:
        return
    is_playing = True
    status_label.config(text="Playing...")
    play_thread = Thread(target=play_midi_file, args=(midi_path_label['text'],), daemon=True)
    play_thread.start()

def stop_play():
    global is_playing
    if is_playing:
        is_playing = False
        status_label.config(text="Stopped.")

def select_midi_file():
    path = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid *.midi")])
    if path:
        midi_path_label.config(text=path)
        midi_filename_label.config(text=os.path.basename(path))
        status_label.config(text="MIDI loaded.")

def toggle_key_limit():
    global limit_to_61_keys
    limit_to_61_keys = not limit_to_61_keys
    outrange_status_label.config(text=f"61-Key Limit: {'ON' if limit_to_61_keys else 'OFF'}")

def toggle_velocity_mode():
    global use_velocity
    use_velocity = not use_velocity
    velocity_status_label.config(text=f"Velocity Mode: {'ON' if use_velocity else 'OFF'}")

def handle_keypress(key):
    try:
        if key.char == '=':
            start_play()
        elif key.char == '-':
            stop_play()
    except AttributeError:
        pass

def start_global_key_listener():
    listener = KeyboardListener(on_press=handle_keypress)
    listener.daemon = True
    listener.start()

def draw_background(canvas, w, h):
    spacing = 20
    for x in range(0, w, spacing):
        canvas.create_line(x, 0, x - h, h, fill="#444")
        canvas.create_line(x, 0, x + h, h, fill="#444")

root = Tk()
root.title("MIDI Autoplayer")
root.geometry("480x360")
root.resizable(False, False)

canvas = Canvas(root, width=480, height=360, highlightthickness=0)
canvas.pack(fill="both", expand=True)
canvas.create_rectangle(0, 0, 480, 360, fill="#2e2e2e")
draw_background(canvas, 480, 360)

frame = Frame(root, bg="#2e2e2e")
frame.place(relx=0.5, rely=0.5, anchor="center")

Label(frame, text="MIDI Autoplayer", font=("Segoe UI", 24, "bold"), fg="#eee", bg="#2e2e2e").pack(pady=(10, 0))
Label(frame, text="= to Start   |   - to Stop", font=("Segoe UI", 14), fg="#bbb", bg="#2e2e2e").pack(pady=(5, 20))

Button(frame, text="Select MIDI", font=("Segoe UI", 12), width=20, bg="#444", fg="#eee",
       activebackground="#666", relief="flat", command=select_midi_file).pack(pady=5)

midi_filename_label = Label(frame, text="", font=("Segoe UI", 10), fg="#ccc", bg="#2e2e2e", wraplength=400)
midi_filename_label.pack(pady=5)

midi_path_label = Label(frame, text="", font=("Segoe UI", 8), fg="#555", bg="#2e2e2e", wraplength=400)
midi_path_label.pack()

Button(frame, text="Toggle 61-Key Limit", font=("Segoe UI", 12), width=20, bg="#777", fg="white",
       activebackground="#999", relief="flat", command=toggle_key_limit).pack(pady=5)

outrange_status_label = Label(frame, text="61-Key Limit: ON", font=("Segoe UI", 11), fg="#bbb", bg="#2e2e2e")
outrange_status_label.pack()

Button(frame, text="Toggle Velocity Mode", font=("Segoe UI", 12), width=20, bg="#777", fg="white",
       activebackground="#999", relief="flat", command=toggle_velocity_mode).pack(pady=5)

velocity_status_label = Label(frame, text="Velocity Mode: ON", font=("Segoe UI", 11), fg="#bbb", bg="#2e2e2e")
velocity_status_label.pack()

control_frame = Frame(frame, bg="#2e2e2e")
control_frame.pack(pady=10)

Button(control_frame, text="Play", font=("Segoe UI", 12), width=10, bg="#5a9bd4", fg="white",
       activebackground="#7ab0f7", relief="flat", command=start_play).pack(side="left", padx=10)

Button(control_frame, text="Stop", font=("Segoe UI", 12), width=10, bg="#d9534f", fg="white",
       activebackground="#f06c6b", relief="flat", command=stop_play).pack(side="left", padx=10)

status_label = Label(frame, text="No MIDI loaded.", font=("Segoe UI", 11), fg="#bbb", bg="#2e2e2e")
status_label.pack(pady=10)

start_global_key_listener()
root.mainloop()
