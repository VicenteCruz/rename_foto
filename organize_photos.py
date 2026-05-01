import os
import shutil
import sys
import hashlib
import re
import zipfile
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from PIL import Image, UnidentifiedImageError

# Tentar importar bibliotecas gráficas (padrão do Python)
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk

# Desativar limite de pixels (para 60MP+)
Image.MAX_IMAGE_PIXELS = None

# --- LÓGICA DO PROGRAMA (CORE) ---

def get_file_hash(file_path):
    """Calcula o hash MD5 do ficheiro."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except OSError:
        return None

def extract_date_from_filename(filename):
    """Tenta extrair data e hora do nome do ficheiro."""
    # Padrões com Hora
    patterns_with_time = [
        r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})",
        r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})",
        r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})",
    ]
    # Padrões só Data
    patterns_date = [
        r"(\d{4})(\d{2})(\d{2})",
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{4})_(\d{2})_(\d{2})",
    ]

    for pattern in patterns_with_time:
        match = re.search(pattern, filename)
        if match:
            try:
                year, month, day, h, m, s = map(int, match.groups())
                if (1990 <= year <= datetime.now().year + 1 and 
                    1 <= month <= 12 and 1 <= day <= 31 and 
                    0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                    return datetime(year, month, day, h, m, s, tzinfo=timezone.utc)
            except ValueError:
                continue

    for pattern in patterns_date:
        match = re.search(pattern, filename)
        if match:
            try:
                year, month, day = map(int, match.groups())
                if 1990 <= year <= datetime.now().year + 1 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

def get_date_taken(file_path):
    """Obtém a data real via EXIF ou Nome."""
    # 1. Tentar EXIF
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif()
            if exif_data:
                # 36867 = DateTimeOriginal
                date_str = exif_data.get(36867) or exif_data.get(306)
                if date_str:
                    try:
                        # Data EXIF é usada como Local Time ("o que estava no relógio")
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
    except Exception:
        pass

    # 2. Nome do Ficheiro
    filename = os.path.basename(file_path)
    return extract_date_from_filename(filename)

def organizer_core(source_dir, dest_dir, log_callback, progress_callback, stop_event, time_delta=None, custom_name="", keep_original=True):
    """
    Função principal de organização, desacoplada da interface.
    log_callback: função(msg)
    progress_callback: função(current, total, status_msg)
    stop_event: threading.Event para cancelar
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng'}
    video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.3gp'}
    supported_extensions = image_extensions.union(video_extensions)

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    log_path = os.path.join(dest_dir, f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    stats = {'total_found': 0, 'copied': 0, 'skipped': 0, 'errors': 0}
    
    with open(log_path, "w", encoding="utf-8") as f_log:
        def log(msg, to_gui=True):
            f_log.write(msg + "\n")
            if to_gui and log_callback:
                log_callback(msg)

        log(f"--- INÍCIO: {datetime.now()} ---")
        log(f"Origem: {source_dir}")
        log(f"Destino: {dest_dir}")

        # 1. FASE DE DESCOBERTA
        log("A procurar ficheiros... aguarde.")
        progress_callback(0, 0, "A procurar ficheiros...")
        
        files_to_process = []
        temp_dirs = []

        try:
            for root, dirs, files in os.walk(source_dir):
                if stop_event.is_set(): return
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    full_path = os.path.join(root, file)
                    
                    if ext in supported_extensions:
                        files_to_process.append(full_path)
                    elif ext == '.zip':
                        try:
                            log(f"Extraindo ZIP: {file}")
                            tmp_dir = tempfile.mkdtemp(prefix="zip_extract_")
                            temp_dirs.append(tmp_dir)
                            with zipfile.ZipFile(full_path, 'r') as z:
                                z.extractall(tmp_dir)
                            # Scan recursivo no temp
                            for r, d, f in os.walk(tmp_dir):
                                for subfile in f:
                                    if os.path.splitext(subfile)[1].lower() in supported_extensions:
                                        files_to_process.append(os.path.join(r, subfile))
                        except Exception as e:
                            log(f"[ZIP ERRO] {file}: {e}")

            total = len(files_to_process)
            log(f"Total encontrado: {total} ficheiros.")
            
            # 2. PROCESSAMENTO
            for i, file_path in enumerate(files_to_process):
                if stop_event.is_set():
                    log("Processo cancelado pelo utilizador.")
                    break
                
                current_progress = i + 1
                fname = os.path.basename(file_path)
                progress_callback(current_progress, total, f"A processar: {fname}")

                try:
                    ext = os.path.splitext(fname)[1].lower()
                    date_obj = get_date_taken(file_path)

                    if date_obj:
                        if time_delta:
                            date_obj += time_delta
                        
                        year = date_obj.strftime("%Y")
                        month = date_obj.strftime("%m")
                        day = date_obj.strftime("%d")
                        hms = date_obj.strftime("%H%M%S")
                        
                        target_folder = os.path.join(dest_dir, year, f"{year}_{month}")
                        
                        original_name_no_ext = os.path.splitext(fname)[0]
                        
                        # Construir o nome de forma inteligente
                        name_parts = [f"{year}{month}{day}_{hms}"]
                        if custom_name:
                            name_parts.append(custom_name)
                        if keep_original:
                            name_parts.append(original_name_no_ext)
                        
                        new_name = " - ".join(name_parts) + ext
                    else:
                        target_folder = os.path.join(dest_dir, "REVER_MANUALMENTE")
                        new_name = fname
                    
                    if not os.path.exists(target_folder):
                        os.makedirs(target_folder, exist_ok=True)
                    
                    final_path = os.path.join(target_folder, new_name)

                    # Verificar duplicados
                    if os.path.exists(final_path):
                        src_hash = get_file_hash(file_path)
                        dest_hash = get_file_hash(final_path)
                        
                        if src_hash == dest_hash:
                            log(f"[DUPLICADO] {fname} já existe.", to_gui=False)
                            stats['skipped'] += 1
                            continue
                        else:
                            # Colisão de nome mas conteúdo diferente
                            counter = 1
                            base_part = os.path.splitext(new_name)[0]
                            while os.path.exists(final_path):
                                new_name = f"{base_part}_{counter}{ext}"
                                final_path = os.path.join(target_folder, new_name)
                                if os.path.exists(final_path) and get_file_hash(final_path) == src_hash:
                                    stats['skipped'] += 1
                                    break
                                counter += 1
                            if os.path.exists(final_path) and get_file_hash(final_path) == src_hash:
                                continue

                    shutil.copy2(file_path, final_path)
                    stats['copied'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    log(f"[ERRO] {fname}: {e}")

            # Limpeza
            for tmp in temp_dirs:
                shutil.rmtree(tmp, ignore_errors=True)
            
            log("\n--- RESULTADO FINAL ---")
            log(f"Copiados: {stats['copied']}")
            log(f"Duplicados: {stats['skipped']}")
            log(f"Erros: {stats['errors']}")
            progress_callback(total, total, "Concluído!")
            messagebox.showinfo("Sucesso", f"Processo terminado!\nCopiados: {stats['copied']}\nVeja o relatório na pasta de destino.")

        except Exception as e:
            log(f"Erro Crítico: {e}")
            messagebox.showerror("Erro", f"Ocorreu um erro crítico: {e}")

# --- INTERFACE GRÁFICA (Tkinter) ---

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de Fotos Inteligente")
        self.root.geometry("600x500")
        
        # Estilo
        style = ttk.Style()
        style.configure("TButton", font=("Helvetica", 10), padding=10)
        style.configure("TLabel", font=("Helvetica", 11))
        
        # Título
        lbl_title = tk.Label(root, text="Organizador de Fotos", font=("Helvetica", 16, "bold"), pady=10)
        lbl_title.pack()

        # Frame de Seleção
        frame_inputs = tk.Frame(root, pady=10)
        frame_inputs.pack(fill="x", padx=20)

        # Pasta Origem
        self.source_var = tk.StringVar()
        btn_source = ttk.Button(frame_inputs, text="1. Selecionar Pasta com Fotos (Origem)", command=self.select_source)
        btn_source.pack(fill="x", pady=5)
        self.lbl_source = tk.Label(frame_inputs, textvariable=self.source_var, fg="gray", wraplength=550)
        self.lbl_source.pack()

        # Pasta Destino
        self.dest_var = tk.StringVar()
        btn_dest = ttk.Button(frame_inputs, text="2. Selecionar Onde Guardar (Destino)", command=self.select_dest)
        btn_dest.pack(fill="x", pady=5)
        self.lbl_dest = tk.Label(frame_inputs, textvariable=self.dest_var, fg="gray", wraplength=550)
        self.lbl_dest.pack()

        # Correção de Tempo
        frame_time = tk.LabelFrame(root, text="Correção de Tempo (Opcional)", pady=5)
        frame_time.pack(fill="x", padx=20, pady=5)
        
        self.time_corr_var = tk.BooleanVar(value=False)
        chk_time = tk.Checkbutton(frame_time, text="Ativar correção de horas", variable=self.time_corr_var)
        chk_time.pack(side="left", padx=5)
        
        tk.Label(frame_time, text="H:").pack(side="left")
        self.hours_var = tk.Entry(frame_time, width=4)
        self.hours_var.insert(0, "-11")
        self.hours_var.pack(side="left", padx=2)
        
        tk.Label(frame_time, text="M:").pack(side="left")
        self.mins_var = tk.Entry(frame_time, width=4)
        self.mins_var.insert(0, "-4")
        self.mins_var.pack(side="left", padx=2)
        
        tk.Label(frame_time, text="S:").pack(side="left")
        self.secs_var = tk.Entry(frame_time, width=4)
        self.secs_var.insert(0, "0")
        self.secs_var.pack(side="left", padx=2)

        # Configurações de Nome
        frame_name = tk.LabelFrame(root, text="Configurações de Nome", pady=5)
        frame_name.pack(fill="x", padx=20, pady=5)

        tk.Label(frame_name, text="Nome Personalizado:").pack(side="left", padx=5)
        self.custom_name_var = tk.Entry(frame_name, width=20)
        self.custom_name_var.pack(side="left", padx=5)

        self.keep_original_var = tk.BooleanVar(value=True)
        chk_original = tk.Checkbutton(frame_name, text="Manter nome original", variable=self.keep_original_var)
        chk_original.pack(side="left", padx=10)

        # Botão Iniciar
        self.btn_start = tk.Button(root, text="INICIAR ORGANIZAÇÃO", font=("Helvetica", 12, "bold"), 
                                   bg="#4CAF50", fg="white", height=2, command=self.start_thread)
        self.btn_start.pack(fill="x", padx=40, pady=20)

        # Progresso
        self.progress = ttk.Progressbar(root, orient="horizontal", length=100, mode='determinate')
        self.progress.pack(fill="x", padx=20)
        self.lbl_status = tk.Label(root, text="A aguardar...", font=("Helvetica", 9))
        self.lbl_status.pack(pady=5)

        # Log
        self.txt_log = scrolledtext.ScrolledText(root, height=8, font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=10)

        self.stop_event = threading.Event()
        self.working = False

    def select_source(self):
        path = filedialog.askdirectory(title="Selecione a pasta onde estão as fotos misturadas")
        if path:
            self.source_var.set(path)
            # Sugerir destino automaticamente
            if not self.dest_var.get():
                parent = os.path.dirname(path)
                suggested = os.path.join(parent, "Fotos_Organizadas")
                self.dest_var.set(suggested)

    def select_dest(self):
        path = filedialog.askdirectory(title="Selecione onde criar a pasta organizada")
        if path:
            self.dest_var.set(path)

    def log(self, message):
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

    def update_progress(self, current, total, msg):
        # Atualiza a GUI (deve ser thread-safe, mas Tkinter tolera chamadas simples)
        self.lbl_status.config(text=f"{msg} ({current}/{total})")
        if total > 0:
            perc = (current / total) * 100
            self.progress['value'] = perc

    def start_thread(self):
        src = self.source_var.get()
        dst = self.dest_var.get()

        if not src or not dst:
            messagebox.showwarning("Atenção", "Por favor selecione a pasta de Origem e de Destino.")
            return

        if self.working:
            return

        time_delta = None
        if self.time_corr_var.get():
            try:
                h = int(self.hours_var.get() or 0)
                m = int(self.mins_var.get() or 0)
                s = int(self.secs_var.get() or 0)
                time_delta = timedelta(hours=h, minutes=m, seconds=s)
            except ValueError:
                messagebox.showerror("Erro", "Os valores de tempo devem ser números inteiros.")
                return

        self.working = True
        self.btn_start.config(state="disabled", text="A Processar...")
        self.stop_event.clear()
        
        self.txt_log.delete(1.0, tk.END)

        custom_name = self.custom_name_var.get().strip()
        keep_original = self.keep_original_var.get()

        t = threading.Thread(target=self.run_process, args=(src, dst, time_delta, custom_name, keep_original))
        t.start()

    def run_process(self, src, dst, time_delta, custom_name, keep_original):
        organizer_core(src, dst, self.log, self.update_progress, self.stop_event, time_delta, custom_name, keep_original)
        self.working = False
        self.btn_start.config(state="normal", text="INICIAR ORGANIZAÇÃO")

def main():
    root = tk.Tk()
    app = App(root)
    
    # Se receber argumentos (drag and drop no exe), preenche a origem automaticamente
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        source = sys.argv[1]
        app.source_var.set(source)
        # Sugere destino
        parent = os.path.dirname(source)
        suggested = os.path.join(parent, "Fotos_Organizadas")
        app.dest_var.set(suggested)
        app.log(f"Pasta detetada via 'Drag & Drop': {source}")

    root.mainloop()

if __name__ == "__main__":
    main()
