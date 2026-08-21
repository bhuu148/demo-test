import cv2
import torch
import pytesseract
import pyttsx3
import warnings
from deep_sort_realtime.deepsort_tracker import DeepSort
from datetime import datetime

# Suppress warnings
warnings.filterwarnings("ignore")

# Tesseract path (if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load YOLOv5n
model = torch.hub.load('ultralytics/yolov5', 'yolov5n', trust_repo=True)
model.eval()

# Deep SORT Tracker
tracker = DeepSort(max_age=5)

# Text-to-Speech Engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)

# Video source
video_path = 'test_video3.mp4'
cap = cv2.VideoCapture(video_path)

# COCO classes
class_names = model.names

# Spoken object memory: {track_id: (label, direction)}
spoken_memory = {}

# Log file path
log_file_path = "object_log.txt"

# === Distance Estimation Function ===
def estimate_distance(object_height_pixels, real_height=1.7, focal_length=615):
    if object_height_pixels == 0:
        return None
    return round((real_height * focal_length) / object_height_pixels, 2)  # meters

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    resized = cv2.resize(frame, (640, 480))
    results = model(resized)
    detections = results.xyxy[0]

    det_list = []
    for *box, conf, cls in detections:
        x1, y1, x2, y2 = [int(i) for i in box]
        label = class_names[int(cls)]
        det_list.append(([x1, y1, x2 - x1, y2 - y1], conf.item(), label))

    tracks = tracker.update_tracks(det_list, frame=resized)

    to_speak = []
    for track in tracks:
        if not track.is_confirmed():
            continue

        l, t, w, h = track.to_ltrb()
        track_id = track.track_id
        label = track.get_det_class()

        center_x = int(l + w / 2)
        direction = "left" if center_x < resized.shape[1] // 3 else "center" if center_x < (2 * resized.shape[1]) // 3 else "right"

        # === Estimate distance in meters ===
        distance = estimate_distance(h)
        distance_str = f"{distance} meters" if distance else "unknown distance"

        # Avoid repeating same info
        if spoken_memory.get(track_id) != (label, direction):
            to_speak.append((label, direction, distance_str))
            spoken_memory[track_id] = (label, direction)

        # Draw bounding box with distance
        cv2.rectangle(resized, (int(l), int(t)), (int(l + w), int(t + h)), (255, 0, 0), 2)
        cv2.putText(resized, f'{label} #{track_id} ({direction}, {distance_str})',
                    (int(l), int(t) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    # Speak and log new detections
    if to_speak:
        sentence = "Detected: " + ", ".join(f"{label} on the {dir} at {dist}" for label, dir, dist in to_speak)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {sentence}\n"

        print(log_entry.strip())
        engine.say(sentence)
        engine.runAndWait()
        engine.stop()  # 🔧 Prevents speech engine from freezing after first call

        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

    cv2.imshow('Blind Assistance View', resized)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()


