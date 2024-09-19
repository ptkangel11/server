import os
import qbittorrentapi
import speedtest
import time
import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters
from telegram import ReplyKeyboardMarkup

# Configurações
GOFILE_API_KEY = "KIxsOddlMz2Iy9Bbng0e3Yke2QsUEr3j"
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'

# Diretório temporário para armazenamento de torrents
TEMP_DOWNLOAD_PATH = "./Torrent/"

# Conectar ao cliente qBittorrent local
qb = qbittorrentapi.Client(host='localhost', port=8080)

# Função para verificar se a conexão está funcionando
def check_qbittorrent_connection():
    try:
        qb.auth_log_in()  # Testa a conexão
    except qbittorrentapi.LoginFailed as e:
        print(f"Erro ao conectar no qBittorrent: {e}")
        raise

# Função para adicionar torrent via link magnet ou arquivo .torrent
def qbittorrent_add_torrent(torrent_link):
    try:
        # Adicionar o torrent via link magnet ou URL
        qb.torrents_add(urls=torrent_link, save_path=TEMP_DOWNLOAD_PATH)
        return "Torrent adicionado com sucesso!"
    except Exception as e:
        raise Exception(f"Erro ao adicionar o torrent: {e}")

# Função para monitorar o progresso do torrent
def qbittorrent_get_torrents():
    try:
        torrents = qb.torrents_info()  # Pegar informações de todos os torrents
        return torrents
    except Exception as e:
        raise Exception(f"Erro ao obter informações dos torrents: {e}")

# Função para fazer upload do arquivo usando a API do GoFile
def upload_file_gofile(file_path):
    try:
        url = "https://api.gofile.io/uploadFile"
        with open(file_path, 'rb') as file:
            response = requests.post(url, files={'file': file}, data={'token': GOFILE_API_KEY})
        
        if response.status_code == 200 and response.json().get('status') == 'ok':
            download_link = response.json()['data']['downloadPage']
            return f"Upload concluído! Link: {download_link}"
        else:
            return "Erro no upload para o GoFile."
    except Exception as e:
        print(f"Erro ao enviar o arquivo para o GoFile: {e}")
        return None

# Função para deletar o arquivo após o upload
def delete_local_file(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return f"Arquivo {file_path} deletado com sucesso."
        else:
            return "Arquivo não encontrado para deletar."
    except Exception as e:
        return f"Erro ao deletar o arquivo: {e}"

# Função para baixar torrent usando qBittorrent e fazer upload para GoFile
async def start_download(update: Update, context: CallbackContext) -> None:
    if len(context.args) == 0:
        await update.message.reply_text("Por favor, forneça um link magnet ou um URL de arquivo torrent.")
        return
    
    link = context.args[0]
    
    try:
        qbittorrent_add_torrent(link)
        await update.message.reply_text(f'Baixando `{link}`... Monitorando progresso.')
    except Exception as e:
        await update.message.reply_text(f"Erro ao adicionar o torrent: {e}")
        return

    # Monitorar progresso
    while True:
        torrents = qbittorrent_get_torrents()
        if not torrents:
            await update.message.reply_text("Nenhum torrent encontrado.")
            break

        for torrent in torrents:
            progress_message = (
                f'{torrent.name} - {torrent.progress * 100:.2f}% completo\n'
                f'Download: {torrent.dlspeed / 1000:.1f} kB/s\n'
                f'Upload: {torrent.upspeed / 1000:.1f} kB/s\n'
                f'Peers: {torrent.num_complete}\n'
                f'Estado: {torrent.state}'
            )
            await update.message.reply_text(progress_message)

            # Se o download estiver concluído
            if torrent.state == "uploading":
                file_path = os.path.join(TEMP_DOWNLOAD_PATH, torrent.name)
                gofile_response = upload_file_gofile(file_path)
                if gofile_response:
                    await update.message.reply_text(gofile_response)
                    
                    # Deletar arquivo após upload
                    deletion_message = delete_local_file(file_path)
                    await update.message.reply_text(deletion_message)
                else:
                    await update.message.reply_text("Erro ao fazer upload do arquivo com GoFile.")
                return

        time.sleep(5)

# Inicializar o bot com a nova forma de construção
application = Application.builder().token(bot_token).build()

# Configurar comandos do bot
application.add_handler(CommandHandler('start_download', start_download))

# Iniciar o bot
application.run_polling()
