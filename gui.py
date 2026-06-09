#!/usr/bin/env python3
"""GUI launcher for extract_driver_docs.py."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path

import extract_driver_docs as extractor


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Driver Docs Extractor")
        self.resizable(False, False)

        pad = {"padx": 10, "pady": 6}

        # Input directory row
        tk.Label(self, text="Input Directory:", anchor="w").grid(row=0, column=0, sticky="w", **pad)
        self.input_var = tk.StringVar(value=str(extractor.SOURCE_DIR))
        tk.Entry(self, textvariable=self.input_var, width=55).grid(row=0, column=1, **pad)
        tk.Button(self, text="Browse…", command=self._browse_input).grid(row=0, column=2, padx=(0, 10))

        # Output directory row
        tk.Label(self, text="Output Directory:", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar(value=str(extractor.OUTPUT_DIR))
        tk.Entry(self, textvariable=self.output_var, width=55).grid(row=1, column=1, **pad)
        tk.Button(self, text="Browse…", command=self._browse_output).grid(row=1, column=2, padx=(0, 10))

        # Run button
        self.run_btn = tk.Button(self, text="Run", width=12, command=self._run)
        self.run_btn.grid(row=2, column=0, columnspan=3, pady=(4, 8))

        # Log output
        self.log = scrolledtext.ScrolledText(self, width=80, height=18, state="disabled", font=("Courier", 11))
        self.log.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 10))

    # ------------------------------------------------------------------

    def _browse_input(self):
        path = filedialog.askdirectory(title="Select Input Directory", initialdir=self.input_var.get())
        if path:
            self.input_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory", initialdir=self.output_var.get())
        if path:
            self.output_var.set(path)

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()

        if not src or not Path(src).is_dir():
            messagebox.showerror("Error", "Input directory does not exist.")
            return
        if not out:
            messagebox.showerror("Error", "Please select an output directory.")
            return

        self.run_btn.configure(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        def worker():
            import io, sys
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf

            try:
                extractor.main(source_dir=src, output_dir=out)
            except Exception as exc:
                sys.stdout = old_stdout
                self.after(0, self._log, f"ERROR: {exc}")
            else:
                sys.stdout = old_stdout
                for line in buf.getvalue().splitlines():
                    self.after(0, self._log, line)
            finally:
                sys.stdout = old_stdout
                self.after(0, self.run_btn.configure, {"state": "normal"})

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
