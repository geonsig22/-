import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from converter import FORMATS, RAW_EXTENSIONS, convert

SUPPORTED = RAW_EXTENSIONS | {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("사진 일괄 변환기")
        asset_dir = Path(__file__).resolve().parent / "assets"
        if (asset_dir / "photobatch.png").exists():
            self.window_icon = tk.PhotoImage(file=str(asset_dir / "photobatch.png"))
            self.iconphoto(True, self.window_icon)
        self.geometry("780x620")
        self.minsize(680, 540)
        self.files = []
        self.events = queue.Queue()
        self.busy = False
        self.cancel = threading.Event()
        self.output = tk.StringVar()
        self.format = tk.StringVar(value="JPG")
        self.quality = tk.StringVar(value="95")
        self.size = tk.StringVar(value="0")
        self.target = tk.StringVar(value="8192")
        self.preset = tk.StringVar(value="고화질 공유용 (최대 8MB)")
        self.status = tk.StringVar(value="변환할 사진을 추가하세요.")
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="사진 일괄 변환기", font=("맑은 고딕", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text="DNG → JPG · 사진 크기 조절 · 원본 보존").pack(anchor="w", pady=(4, 4))
        ttk.Label(frame, text="원본은 수정하지 않습니다. 결과는 새 파일로 저장합니다.", foreground="#087f5b").pack(anchor="w", pady=(0, 10))
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        self.controls = []
        for label, command in [("사진 추가", self.add_files), ("폴더 추가", self.add_folder), ("목록 비우기", self.clear)]:
            button = ttk.Button(bar, text=label, command=command)
            button.pack(side="left", padx=(0, 8))
            self.controls.append(button)
        self.listbox = tk.Listbox(frame, height=9)
        self.listbox.pack(fill="both", expand=True, pady=10)
        output_row = ttk.Frame(frame)
        output_row.pack(fill="x")
        ttk.Label(output_row, text="저장 폴더").pack(side="left")
        entry = ttk.Entry(output_row, textvariable=self.output)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        button = ttk.Button(output_row, text="찾아보기", command=self.choose_output)
        button.pack(side="left")
        self.controls.extend([entry, button])
        preset_row = ttk.Frame(frame)
        preset_row.pack(fill="x", pady=(12, 0))
        ttk.Label(preset_row, text="용도별 설정").pack(side="left", padx=(0, 8))
        preset = ttk.Combobox(preset_row, textvariable=self.preset, state="readonly", width=24,
                              values=["고화질 공유용 (최대 8MB)", "고화질 (용량 제한 없음)", "직접 설정", "카카오톡 공유용 (작은 용량)", "작은 파일로 공유", "20MB 이하로 줄이기"])
        preset.pack(side="left")
        preset.bind("<<ComboboxSelected>>", self.apply_preset)
        ttk.Label(preset_row, text="사진당 목표 KB (0=제한 없음)").pack(side="left", padx=8)
        target = ttk.Entry(preset_row, textvariable=self.target, width=8)
        target.pack(side="left")
        self.controls.extend([preset, target])
        settings = ttk.Frame(frame)
        settings.pack(fill="x", pady=14)
        for label, variable in [("출력 형식", self.format), ("화질 (1~100)", self.quality), ("최대 변 길이(px, 0=유지)", self.size)]:
            ttk.Label(settings, text=label).pack(side="left", padx=(0, 5))
            widget = ttk.Combobox(settings, textvariable=variable, values=list(FORMATS), state="readonly", width=7) if variable is self.format else ttk.Entry(settings, textvariable=variable, width=7)
            widget.pack(side="left", padx=(0, 12))
            self.controls.append(widget)
        ttk.Label(frame, text="목표 용량에 맞춰 화질·해상도를 자동으로 낮춥니다. PNG는 해상도만 조절합니다.\n메타데이터는 유지하지 않습니다. DNG 색감은 카메라 미리보기와 다를 수 있습니다.").pack(anchor="w")
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=12)
        self.start_button = ttk.Button(actions, text="변환 시작", command=self.start)
        self.start_button.pack(side="left")
        self.controls.append(self.start_button)
        self.stop_button = ttk.Button(actions, text="중지", command=self.cancel.set, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(frame)
        self.progress.pack(fill="x")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=5)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def add(self, paths):
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() in SUPPORTED and path not in self.files:
                self.files.append(path)
                self.listbox.insert("end", str(path))
        self.status.set(f"{len(self.files)}개 사진 선택됨")
        if self.files and not self.output.get():
            self.output.set(str(self.files[0].parent / "converted"))

    def add_files(self):
        self.add(filedialog.askopenfilenames(title="변환할 사진 선택"))

    def add_folder(self):
        folder = filedialog.askdirectory(title="사진 폴더 선택 (하위 폴더 제외)")
        if folder:
            self.add(p for p in Path(folder).iterdir() if p.is_file())

    def choose_output(self):
        folder = filedialog.askdirectory(title="결과 저장 폴더 선택")
        if folder:
            self.output.set(folder)

    def clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")
        self.status.set("변환할 사진을 추가하세요.")

    def apply_preset(self, event=None):
        presets = {"카카오톡 공유용 (작은 용량)": (85, 1920, 1024), "작은 파일로 공유": (75, 1280, 300),
                   "20MB 이하로 줄이기": (95, 0, 20480), "고화질 공유용 (최대 8MB)": (95, 0, 8192),
                   "고화질 (용량 제한 없음)": (95, 0, 0)}
        if self.preset.get() in presets:
            quality, size, target = presets[self.preset.get()]
            self.format.set("JPG")
            self.quality.set(str(quality))
            self.size.set(str(size))
            self.target.set(str(target))

    def start(self):
        try:
            quality, size, target = int(self.quality.get()), int(self.size.get()), int(self.target.get())
            if not 1 <= quality <= 100 or size < 0 or target < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("입력 확인", "화질은 1~100, 최대 길이·목표 KB는 0 이상의 정수를 입력하세요.")
            return
        if not self.files or not self.output.get().strip():
            messagebox.showerror("입력 확인", "사진과 저장 폴더를 선택하세요.")
            return
        self.busy = True
        self.cancel.clear()
        for control in self.controls:
            control.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress.configure(maximum=len(self.files), value=0)
        args = (tuple(self.files), self.output.get(), self.format.get(), quality, size, target)
        threading.Thread(target=self.work, args=args, daemon=True).start()

    def work(self, files, output, format_name, quality, size, target):
        started = time.perf_counter()
        success, errors, before, after = 0, [], 0, 0
        for index, source in enumerate(files, 1):
            if self.cancel.is_set():
                break
            self.events.put(("working", index, source.name))
            try:
                original_bytes = source.stat().st_size
                result = convert(source, output, format_name, quality, size, target)
                before += original_bytes
                after += result.stat().st_size
                success += 1
            except Exception as error:
                errors.append(f"{source.name}: {error}")
            self.events.put(("progress", index, source.name))
        self.events.put(("done", success, errors, before, after, self.cancel.is_set(), time.perf_counter() - started))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "working":
                    self.status.set(f"{event[1]}/{len(self.files)} 변환 중: {event[2]}")
                elif event[0] == "progress":
                    self.progress.configure(value=event[1])
                    self.status.set(f"{event[1]}/{len(self.files)} 처리: {event[2]}")
                else:
                    _, count, errors, before, after, cancelled, elapsed = event
                    self.busy = False
                    for control in self.controls:
                        control.configure(state="readonly" if isinstance(control, ttk.Combobox) else "normal")
                    self.stop_button.configure(state="disabled")
                    text = f"{'중지됨' if cancelled else '완료'} · 성공 {count}개 · 실패 {len(errors)}개"
                    if before:
                        text += f" · {before / 1048576:.1f} → {after / 1048576:.1f} MB"
                    text += f" · {elapsed:.1f}초"
                    self.status.set(text)
                    if errors:
                        window = tk.Toplevel(self)
                        window.title("변환 실패 목록")
                        details = tk.Text(window, wrap="word", width=90, height=20)
                        details.pack(fill="both", expand=True)
                        details.insert("1.0", "\n".join(errors))
                        details.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("변환 중", "중지를 누르고 현재 사진 처리가 끝난 뒤 닫아주세요.")
        else:
            self.destroy()


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        import tempfile
        import rawpy
        from PIL import Image
        asset_dir = Path(__file__).resolve().parent / "assets"
        if getattr(sys, "frozen", False) and not (asset_dir / "photobatch.png").is_file():
            raise RuntimeError("Packaged icon is missing")
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "test.png"
            Image.new("RGB", (32, 16), "red").save(source)
            result = convert(source, folder, "JPG", 85, 16, 20)
            with Image.open(result) as image:
                if image.size != (16, 8) or image.format != "JPEG":
                    raise RuntimeError("Packaged converter self-test failed")
    else:
        Application().mainloop()
