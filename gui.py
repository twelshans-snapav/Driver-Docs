#!/usr/bin/env python3
"""GUI launcher for extract_driver_docs.py."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path

import extract_driver_docs as extractor


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Driver Docs Extractor")
        self.resizable(False, False)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        run_tab = ttk.Frame(notebook)
        terms_tab = ttk.Frame(notebook)
        notebook.add(run_tab, text="Run")
        notebook.add(terms_tab, text="Term Corrections")

        self._build_run_tab(run_tab)
        self._build_terms_tab(terms_tab)

    # ------------------------------------------------------------------
    # Run tab
    # ------------------------------------------------------------------

    def _build_run_tab(self, parent):
        pad = {"padx": 10, "pady": 6}

        tk.Label(parent, text="Input Directory:", anchor="w").grid(row=0, column=0, sticky="w", **pad)
        self.input_var = tk.StringVar(value=str(extractor.SOURCE_DIR))
        tk.Entry(parent, textvariable=self.input_var, width=55).grid(row=0, column=1, **pad)
        tk.Button(parent, text="Browse…", command=self._browse_input).grid(row=0, column=2, padx=(0, 10))

        tk.Label(parent, text="Output Directory:", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar(value=str(extractor.OUTPUT_DIR))
        tk.Entry(parent, textvariable=self.output_var, width=55).grid(row=1, column=1, **pad)
        tk.Button(parent, text="Browse…", command=self._browse_output).grid(row=1, column=2, padx=(0, 10))

        self.run_btn = tk.Button(parent, text="Run", width=12, command=self._run)
        self.run_btn.grid(row=2, column=0, columnspan=3, pady=(4, 8))

        self.log = scrolledtext.ScrolledText(parent, width=80, height=18, state="disabled", font=("Courier", 11))
        self.log.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 10))

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

    # ------------------------------------------------------------------
    # Term Corrections tab
    # ------------------------------------------------------------------

    def _build_terms_tab(self, parent):
        # List of current terms
        list_frame = tk.Frame(parent)
        list_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 4), sticky="ew")

        tk.Label(list_frame, text="Key (lowercase)").grid(row=0, column=0, padx=(0, 20))
        tk.Label(list_frame, text="Replacement").grid(row=0, column=1)

        self.terms_list = tk.Listbox(list_frame, width=60, height=16, font=("Courier", 11),
                                     selectmode="single", exportselection=False)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.terms_list.yview)
        self.terms_list.configure(yscrollcommand=scrollbar.set)
        self.terms_list.grid(row=1, column=0, columnspan=2, sticky="nsew")
        scrollbar.grid(row=1, column=2, sticky="ns")
        self.terms_list.bind("<<ListboxSelect>>", self._on_term_select)

        self._refresh_terms_list()

        # Add / edit row
        add_frame = tk.Frame(parent)
        add_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=6)

        tk.Label(add_frame, text="Key:").grid(row=0, column=0, padx=(0, 4))
        self.key_var = tk.StringVar()
        self.key_entry = tk.Entry(add_frame, textvariable=self.key_var, width=20)
        self.key_entry.grid(row=0, column=1, padx=(0, 12))

        tk.Label(add_frame, text="Replacement:").grid(row=0, column=2, padx=(0, 4))
        self.val_var = tk.StringVar()
        self.val_entry = tk.Entry(add_frame, textvariable=self.val_var, width=24)
        self.val_entry.grid(row=0, column=3, padx=(0, 12))

        tk.Button(add_frame, text="Add / Update", command=self._add_term).grid(row=0, column=4, padx=(0, 6))
        tk.Button(add_frame, text="Remove Selected", command=self._remove_term).grid(row=0, column=5)

    def _refresh_terms_list(self):
        self.terms_list.delete(0, "end")
        for key in sorted(extractor.TERM_CORRECTIONS):
            self.terms_list.insert("end", f"{key:<20}  →  {extractor.TERM_CORRECTIONS[key]}")

    def _on_term_select(self, _event):
        sel = self.terms_list.curselection()
        if not sel:
            return
        key = sorted(extractor.TERM_CORRECTIONS)[sel[0]]
        self.key_var.set(key)
        self.val_var.set(extractor.TERM_CORRECTIONS[key])

    def _add_term(self):
        key = self.key_var.get().strip().lower()
        val = self.val_var.get().strip()
        if not key:
            messagebox.showerror("Error", "Key cannot be empty.")
            return
        if not val:
            messagebox.showerror("Error", "Replacement cannot be empty.")
            return
        extractor.TERM_CORRECTIONS[key] = val
        self._refresh_terms_list()
        self.key_var.set("")
        self.val_var.set("")

    def _remove_term(self):
        sel = self.terms_list.curselection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select a term to remove.")
            return
        key = sorted(extractor.TERM_CORRECTIONS)[sel[0]]
        del extractor.TERM_CORRECTIONS[key]
        self._refresh_terms_list()
        self.key_var.set("")
        self.val_var.set("")


if __name__ == "__main__":
    App().mainloop()
