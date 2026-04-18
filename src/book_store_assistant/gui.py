"""Simple tkinter GUI for librarians to process ISBN files."""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from book_store_assistant.bibliographic.export import (
    export_handoff_results,
    export_review_rows,
    export_upload_records,
)
from book_store_assistant.pipeline.service import process_isbn_file
from book_store_assistant.sources.results import FetchResult


class BookStoreAssistantApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Book Store Assistant")
        self.root.resizable(False, False)

        # Center content in a frame with padding
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -- 1. Label --
        ttk.Label(main_frame, text="Seleccionar archivo de ISBNs:").pack(anchor=tk.W)

        # -- 2. File picker row --
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(4, 12))

        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly")
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(file_frame, text="Examinar...", command=self._browse_file).pack(side=tk.RIGHT)

        # -- 3. Process button --
        self.process_button = ttk.Button(
            main_frame, text="Procesar", command=self._start_processing
        )
        self.process_button.pack(pady=(0, 12))

        # -- 4. Progress bar --
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            main_frame, variable=self.progress_var, maximum=100, mode="determinate", length=460
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))

        # -- 5. Status label --
        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 12))

        # -- 6. Results frame (hidden until processing completes) --
        self.results_frame = ttk.LabelFrame(main_frame, text="Resultados", padding=10)
        self.upload_count_var = tk.StringVar()
        self.review_count_var = tk.StringVar()
        self.total_count_var = tk.StringVar()
        self.duplicate_count_var = tk.StringVar()

        ttk.Label(self.results_frame, textvariable=self.upload_count_var).pack(anchor=tk.W)
        ttk.Label(self.results_frame, textvariable=self.review_count_var).pack(anchor=tk.W)
        ttk.Label(self.results_frame, textvariable=self.total_count_var).pack(anchor=tk.W)
        self.duplicate_count_label = ttk.Label(
            self.results_frame, textvariable=self.duplicate_count_var
        )

        # Set a reasonable minimum window size
        self.root.update_idletasks()
        self.root.minsize(500, self.root.winfo_reqheight())
        self.root.geometry("500x{}".format(max(self.root.winfo_reqheight(), 280)))

    # ------------------------------------------------------------------ #
    # File picker
    # ------------------------------------------------------------------ #
    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de ISBNs",
            filetypes=[
                ("Archivos Excel", "*.xlsx"),
                ("Archivos CSV", "*.csv"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if path:
            self.file_path_var.set(path)

    # ------------------------------------------------------------------ #
    # Derive output paths from the input path
    # ------------------------------------------------------------------ #
    @staticmethod
    def _output_paths(input_path: Path) -> tuple[Path, Path, Path]:
        stem = input_path.stem
        parent = input_path.parent
        upload_path = parent / f"{stem}_upload.xlsx"
        review_path = parent / f"{stem}_review.xlsx"
        handoff_path = parent / f"{stem}_handoff.jsonl"
        return upload_path, review_path, handoff_path

    # ------------------------------------------------------------------ #
    # Processing
    # ------------------------------------------------------------------ #
    def _start_processing(self) -> None:
        file_path = self.file_path_var.get().strip()
        if not file_path:
            messagebox.showwarning("Advertencia", "Por favor seleccione un archivo primero.")
            return

        input_path = Path(file_path)
        if not input_path.is_file():
            messagebox.showerror("Error", f"El archivo no existe:\n{input_path}")
            return

        # Disable button and reset UI
        self.process_button.configure(state=tk.DISABLED)
        self.progress_var.set(0.0)
        self.status_var.set("Iniciando...")
        self.results_frame.pack_forget()

        thread = threading.Thread(target=self._worker, args=(input_path,), daemon=True)
        thread.start()

    def _worker(self, input_path: Path) -> None:
        """Runs in a background thread. All GUI updates go through root.after()."""
        try:
            result = process_isbn_file(
                input_path,
                on_fetch_start=self._on_fetch_start,
                on_fetch_complete=self._on_fetch_complete,
                on_status_update=self._on_status_update,
            )

            # Export outputs
            upload_path, review_path, handoff_path = self._output_paths(input_path)

            self._schedule_status("Exportando resultados...")
            export_upload_records(result.resolution_results, upload_path)
            export_review_rows(result.resolution_results, review_path)
            export_handoff_results(result.resolution_results, handoff_path)

            # Compute counts
            upload_count = sum(1 for r in result.resolution_results if r.record is not None)
            review_count = sum(1 for r in result.resolution_results if r.record is None)
            total = len(result.resolution_results)
            duplicate_count = result.input_result.duplicate_count

            # Schedule completion UI update on main thread
            self.root.after(
                0,
                self._on_complete,
                upload_count,
                review_count,
                total,
                duplicate_count,
                upload_path,
                review_path,
                handoff_path,
            )

        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))

    # ------------------------------------------------------------------ #
    # Callbacks (called from worker thread, schedule GUI updates)
    # ------------------------------------------------------------------ #
    def _on_fetch_start(self, index: int, total: int, isbn: str) -> None:
        pct = (index - 1) / total * 100 if total > 0 else 0
        self.root.after(0, self._update_progress, pct, f"Procesando ISBN {index}/{total}: {isbn}")

    def _on_fetch_complete(self, index: int, total: int, result: FetchResult) -> None:
        pct = index / total * 100 if total > 0 else 0
        self.root.after(0, self._update_progress, pct, f"ISBN {index}/{total} completado.")

    def _on_status_update(self, message: str) -> None:
        self.root.after(0, self._schedule_status_impl, message)

    def _schedule_status(self, message: str) -> None:
        """Convenience for scheduling a status update from the worker thread."""
        self.root.after(0, self._schedule_status_impl, message)

    # ------------------------------------------------------------------ #
    # GUI update helpers (always run on the main thread)
    # ------------------------------------------------------------------ #
    def _update_progress(self, pct: float, status: str) -> None:
        self.progress_var.set(pct)
        self.status_var.set(status)

    def _schedule_status_impl(self, message: str) -> None:
        self.status_var.set(message)

    def _on_complete(
        self,
        upload_count: int,
        review_count: int,
        total: int,
        duplicate_count: int,
        upload_path: Path,
        review_path: Path,
        handoff_path: Path,
    ) -> None:
        self.progress_var.set(100.0)
        self.status_var.set("Proceso completado.")
        self.process_button.configure(state=tk.NORMAL)

        # Show results frame
        self.upload_count_var.set(f"Listos para subir: {upload_count}")
        self.review_count_var.set(f"Para revisar: {review_count}")
        self.total_count_var.set(f"Total procesados: {total}")
        if duplicate_count > 0:
            self.duplicate_count_var.set(f"Duplicados eliminados: {duplicate_count}")
            self.duplicate_count_label.pack(anchor=tk.W)
        else:
            self.duplicate_count_label.pack_forget()
        self.results_frame.pack(fill=tk.X, pady=(8, 0))

        duplicate_line = (
            f"  Duplicados eliminados: {duplicate_count}\n" if duplicate_count > 0 else ""
        )
        messagebox.showinfo(
            "Proceso completado",
            (
                f"Se procesaron {total} ISBN(s).\n\n"
                f"  Listos para subir: {upload_count}\n"
                f"  Para revisar: {review_count}\n"
                f"{duplicate_line}\n"
                f"Archivos guardados en:\n"
                f"  {upload_path.name}\n"
                f"  {review_path.name}\n"
                f"  {handoff_path.name}"
            ),
        )

    def _on_error(self, message: str) -> None:
        self.progress_var.set(0.0)
        self.status_var.set("Error durante el proceso.")
        self.process_button.configure(state=tk.NORMAL)
        messagebox.showerror("Error", f"Ocurrio un error durante el proceso:\n\n{message}")


def main() -> None:
    root = tk.Tk()
    BookStoreAssistantApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
