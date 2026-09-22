import tkinter as tk
from tkinter import ttk

_estilo_contador = 0


class BarCarga:
    """Barra de progreso verde + circulo de estado, anclada como pie de página del panel.

    Inactivo: barra detenida y circulo verde fijo.
    En proceso: barra en movimiento y circulo parpadeando en amarillo.
    """

    def __init__(self, parent, bg="black"):
        global _estilo_contador
        _estilo_contador += 1

        self._activo = False
        self._parpadeo_on = False
        self._after_id = None

        self.frame = tk.Frame(parent, bg=bg)

        self._estilo = ttk.Style()
        # El tema por defecto en Windows (vista) ignora los colores personalizados del Progressbar
        if self._estilo.theme_use() != "clam":
            self._estilo.theme_use("clam")
        self._nombre_estilo = f"BarCarga{_estilo_contador}.Horizontal.TProgressbar"
        self._estilo.configure(self._nombre_estilo, background="black", troughcolor="black", bordercolor="black", lightcolor="black", darkcolor="black")

        self._barra = ttk.Progressbar(
            self.frame, orient="horizontal", mode="indeterminate", style=self._nombre_estilo
        )
        self._barra.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._circulo = tk.Canvas(self.frame, width=16, height=16, bg=bg, highlightthickness=0)
        self._circulo.pack(side="left")
        self._circulo_id = self._circulo.create_oval(2, 2, 14, 14, fill="green", outline="")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        self._estilo.configure(self._nombre_estilo, background="green", lightcolor="green", darkcolor="green")
        self._barra.start(12)
        self._parpadear()

    def detener(self):
        self._activo = False
        self._barra.stop()
        self._estilo.configure(self._nombre_estilo, background="black", lightcolor="black", darkcolor="black")
        if self._after_id is not None:
            self._circulo.after_cancel(self._after_id)
            self._after_id = None
        self._circulo.itemconfig(self._circulo_id, fill="green")

    def _parpadear(self):
        if not self._activo:
            return
        self._parpadeo_on = not self._parpadeo_on
        color = "yellow" if self._parpadeo_on else "black"
        self._circulo.itemconfig(self._circulo_id, fill=color)
        self._after_id = self._circulo.after(400, self._parpadear)


class IndicadorEstado:
    """Etiqueta con un círculo de estado que cambia según haya o no dispositivos detectados."""

    def __init__(self, parent, texto, bg="black", fg="white"):
        self.frame = tk.Frame(parent, bg=bg)
        tk.Label(self.frame, text=texto, fg=fg, bg=bg, font=("Arial", 9, "bold")).pack(side="left")
        self._circulo = tk.Canvas(self.frame, width=14, height=14, bg=bg, highlightthickness=0)
        self._circulo.pack(side="left", padx=(4, 0))
        self._circulo_id = self._circulo.create_oval(2, 2, 12, 12, fill="", outline="white")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    def encender(self, color="green"):
        self._circulo.itemconfig(self._circulo_id, fill=color, outline=color)

    def apagar(self):
        self._circulo.itemconfig(self._circulo_id, fill="", outline="white")

    def resultado(self, encontrado):
        if encontrado:
            self.encender("green2")
        else:
            self.encender("red")
