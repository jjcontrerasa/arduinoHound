import tkinter as tk

# Importar módulos desde la carpeta modules
import modules.cargarSketch as cargarSketch
import modules.puertos as puertos
import modules.rastrear as rastrear


# ---------------- CONFIG ----------------
BG_COLOR = "black"
FRAME_BORDER_COLOR = "white"
TITLE = "ArduinoHound V2"

# ---------------- MAIN WINDOW ----------------
root = tk.Tk()
root.title(TITLE)
root.configure(bg=BG_COLOR)
root.state("zoomed")

# Tamaño inicial
root.geometry("1200x720")

# Grid 3 columnas
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=1)
root.columnconfigure(2, weight=1)
root.rowconfigure(0, weight=1)

# ---------------- PANEL IZQUIERDO ----------------
frame_izq = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_izq.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

puertos.crear_panel(frame_izq)

# ---------------- PANEL CENTRAL ----------------
frame_centro = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_centro.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

cargarSketch.crear_panel(frame_centro)

# ---------------- PANEL DERECHO ----------------
frame_der = tk.Frame(
    root,
    bg=BG_COLOR,
    highlightbackground=FRAME_BORDER_COLOR,
    highlightthickness=1
)
frame_der.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

rastrear.crear_panel(frame_der)

# ---------------- AJUSTE DINÁMICO ----------------
def ajustar_ventana(event):
    """
    Control simple para evitar que la ventana se haga demasiado pequeña
    """
    min_width = 900
    min_height = 600

    if root.winfo_width() < min_width:
        root.geometry(f"{min_width}x{root.winfo_height()}")

    if root.winfo_height() < min_height:
        root.geometry(f"{root.winfo_width()}x{min_height}")

root.bind("<Configure>", ajustar_ventana)

# ---------------- START ----------------
if __name__ == "__main__":
    root.mainloop()