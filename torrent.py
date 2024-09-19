import os
import time
import datetime
import libtorrent as lt
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Configurações
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'
GOFILE_API_KEY = "KIxsOddlMz2Iy9Bbng0e3Yke2QsUEr3j"
DOWNLOAD_PATH = "./downloads/"

# Função para fazer upload do arquivo para o GoFile usando CLI
def upload_file_gofile(file_path):
    try:
        # Executar o comando gofilepy com a API key
        result = subprocess.run(['gofilepy', file_path, '-e', f'--token={GOFILE_API_KEY}'], capture_output=True, text=True)
        
        # Verificar se o comando foi bem-sucedido
        if result.returncode == 0:
            # Procurar pela URL de download na saída
            for line in result.stdout.split('\n'):
                if "Download page:" in line:
                    url = line.split()[-1]
                    return f"Upload para GoFile concluído! Link para download: {url}"
        else:
            return f"Erro ao enviar o arquivo: {result.stderr}"
    except Exception as e:
        print(f"Erro ao fazer upload: {e}")
        return None

# ... (resto do código permanece o mesmo)

# Inicializar o bot com a nova forma de construção
application = Application.builder().token(bot_token).build()

# Configurar comandos do bot
application.add_handler(CommandHandler('start_download', start_download))
application.add_handler(CommandHandler('help', show_menu))

# Iniciar o bot
if __name__ == '__main__':
    application.run_polling()
