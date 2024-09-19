import os
import shutil  # Importado para remover diretórios
import qbittorrentapi
import speedtest
import time
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters
from telegram import ReplyKeyboardMarkup

# Configurações
GOFILE_API_KEY = "KIxsOddlMz2Iy9Bbng0e3Yke2QsUEr3j"
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'

# Diretório onde o rclone está montado
RCLONE_MOUNT_PATH = "/mnt/rclone/Torrent/"  # Substitua pelo caminho correto onde o rclone está montado

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
        qb.torrents_add(urls=torrent_link, save_path=RCLONE_MOUNT_PATH)
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

# Função para fazer upload do arquivo para o GoFile usando rclone
def upload_file_rclone(file_path):
    try:
        rclone_upload_command = f'rclone copy "{file_path}" gofile:./Torrent/'
        os.system(rclone_upload_command)

        # Verificar se o arquivo ainda existe localmente (indicando que o upload foi bem-sucedido)
        if not os.path.exists(file_path):  # Arquivo removido
            return f"Upload para GoFile com rclone concluído: {file_path}"
        else:
            return "Erro no upload com rclone para GoFile."
    except Exception as e:
        print(f"Erro ao enviar o arquivo com rclone: {e}")
        return None

# Função para deletar o arquivo ou diretório após o upload
def delete_local_file(file_path):
    try:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Deleta o diretório e todo o seu conteúdo
                return f"Diretório {file_path} deletado com sucesso."
            else:
                os.remove(file_path)  # Deleta arquivo
                return f"Arquivo {file_path} deletado com sucesso."
        else:
            return "Arquivo ou diretório não encontrado para deletar."
    except Exception as e:
        return f"Erro ao deletar o arquivo ou diretório: {e}"

# Comando para realizar o Speedtest
async def run_speedtest(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Executando Speedtest, por favor, aguarde...")

    st = speedtest.Speedtest()
    download_speed = st.download() / 1_000_000  # Mbps
    upload_speed = st.upload() / 1_000_000  # Mbps
    ping = st.results.ping

    response_message = (
        f"**Resultados do Speedtest:**\n"
        f"Download: {download_speed:.2f} Mbps\n"
        f"Upload: {upload_speed:.2f} Mbps\n"
        f"Ping: {ping:.2f} ms"
    )

    await update.message.reply_text(response_message, parse_mode='Markdown')

# Função para mostrar o menu de instruções
async def show_menu(update: Update, context: CallbackContext) -> None:
    menu_message = (
        "Bem-vindo! Aqui estão os comandos disponíveis:\n\n"
        "/start_download <magnet_link ou .torrent URL> - Inicia o download a partir de um link magnet ou torrent.\n"
        "/speedtest - Executa um teste de velocidade de internet.\n"
        "/upload_to_gofile <nome_arquivo> - Faz upload do arquivo para o GoFile.\n"
        "/toggle_bot - Ativa ou desativa o bot.\n"
    )
    await update.message.reply_text(menu_message)

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
                file_path = os.path.join(RCLONE_MOUNT_PATH, torrent.name)
                rclone_response = upload_file_rclone(file_path)
                if rclone_response:
                    await update.message.reply_text(rclone_response)
                    
                    # Deletar arquivo ou diretório após upload
                    deletion_message = delete_local_file(file_path)
                    await update.message.reply_text(deletion_message)
                else:
                    await update.message.reply_text("Erro ao fazer upload do arquivo com rclone.")
                return

        time.sleep(5)

# Criação de um menu flutuante com as opções
def get_reply_keyboard():
    custom_keyboard = [
        ['/start_download', '/speedtest'],
        ['/upload_to_gofile', '/toggle_bot'],
        ['/help']
    ]
    return ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)

# Inicializar o bot com a nova forma de construção
application = Application.builder().token(bot_token).build()

# Configurar comandos do bot
application.add_handler(CommandHandler('start_download', start_download))
application.add_handler(CommandHandler('speedtest', run_speedtest))
application.add_handler(CommandHandler('help', show_menu))

# Configurar o menu flutuante (usando um MessageHandler para capturar a digitação de '/')
async def show_floating_menu(update: Update, context: CallbackContext) -> None:
    reply_markup = get_reply_keyboard()
    await update.message.reply_text("Escolha uma opção:", reply_markup=reply_markup)

# Adicionando o handler do menu flutuante
application.add_handler(MessageHandler(filters.Regex('^/$'), show_floating_menu))

# Iniciar o bot
application.run_polling()
