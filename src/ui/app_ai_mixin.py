"""Mixin — AI text-expansion feature for :class:`Application`."""

from __future__ import annotations

import tkinter as tk
from threading import Thread
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable

from src.ai import AIMessage, create_service


class AppAiMixin:
    """Expand free-text fields using an AI provider."""

    def ai_expand_text(self, original_text: str, callback: Callable[[str], None]) -> None:
        """Ask the configured AI provider to professionalise *original_text*."""
        if not original_text.strip():
            return

        provider = self.ai_provider_var.get().strip() or self.AI_PROVIDERS[0]
        key_map = {
            "Claude": self.claude_api_key_var.get().strip(),
            "Gemini": self.gemini_api_key_var.get().strip(),
            "Gateway": self.gateway_api_key_var.get().strip(),
        }
        key = key_map.get(provider, "")
        if not key:
            messagebox.showwarning(self._t("info_title"), self._t("ai_expand_not_configured"))
            return

        progress_dialog = tk.Toplevel(self)
        progress_dialog.title(self._t("ai_expand_title"))
        progress_dialog.geometry("300x100")
        self._configure_secondary_window(progress_dialog)
        ttk.Label(
            progress_dialog,
            text=self._t("discussion_thinking", provider=provider),
        ).pack(pady=20)
        progress_dialog.update()

        def worker() -> None:
            try:
                settings = {
                    "claude_api_key": self.claude_api_key_var.get(),
                    "gemini_api_key": self.gemini_api_key_var.get(),
                    "gateway_api_key": self.gateway_api_key_var.get(),
                    "gateway_cert_path": self.gateway_cert_path_var.get(),
                    "claude_model": self.claude_model_var.get().strip()
                    or self.DEFAULT_CLAUDE_MODEL,
                    "gemini_model": self.gemini_model_var.get().strip()
                    or self.DEFAULT_GEMINI_MODEL,
                    "gateway_model": self.gateway_model_var.get().strip()
                    or self.DEFAULT_GATEWAY_MODEL,
                }
                service = create_service(provider, settings)
                prompt = self._t("ai_expand_prompt", text=original_text)
                messages = [AIMessage(role="user", content=prompt)]
                reply = service.chat(
                    messages,
                    system_prompt=(
                        "Tu es un expert Salesforce chevronné. "
                        "Tu rédiges des notes techniques concises, professionnelles et percutantes."
                    ),
                )
                self.after(
                    0,
                    lambda: self._show_ai_expand_result(reply, callback, progress_dialog),
                )
            except Exception as exc:
                error_msg = str(exc)
                self.after(
                    0,
                    lambda: [
                        progress_dialog.destroy(),
                        messagebox.showerror(
                            self._t("error_title"), f"Erreur IA : {error_msg}"
                        ),
                    ],
                )

        Thread(target=worker, daemon=True).start()

    def _show_ai_expand_result(
        self,
        new_text: str,
        callback: Callable[[str], None],
        progress_dialog: tk.Toplevel,
    ) -> None:
        progress_dialog.destroy()

        result_window = tk.Toplevel(self)
        result_window.title(self._t("ai_expand_title"))
        result_window.geometry("600x500")
        self._configure_secondary_window(result_window)

        main_frame = ttk.Frame(result_window, padding=16)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame, text=self._t("ai_expand_title"), font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))

        txt = scrolledtext.ScrolledText(main_frame, wrap="word", height=15)
        txt.insert("1.0", new_text)
        txt.pack(fill="both", expand=True, pady=(0, 16))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        def _use() -> None:
            callback(txt.get("1.0", "end-1c").strip())
            result_window.destroy()

        ttk.Button(btn_frame, text=self._t("ai_expand_use"), command=_use).pack(side="right")
        ttk.Button(
            btn_frame,
            text=self._t("ai_expand_discard"),
            command=result_window.destroy,
        ).pack(side="right", padx=(0, 8))
