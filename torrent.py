import os
import time
import datetime
import libtorrent as lt
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from gofilepy import GoFile

# Configurações
GOFILE_API_KEY = "YOUR_GOFILE_API_KEY"  # Substitua com sua chave de API do GoFile
bot_token = 'YOUR_BOT_TOKEN'  # Substitua com seu token do bot do Telegram
DOWNLOAD_PATH = "./downloads/"  # Diretório onde o torrent será baixado

# Instanciação do cliente GoFile
gofile = GoFile(api_key=GOFILE_API_KEY)

# Função para fazer upload do arquivo para o GoFile usando gofilepy
def upload_file_gofile(file_path):
    try:
        # Fazer o upload do arquivo
        response = gofile.upload_file(file_path)
        
        # Verificar se o upload foi bem-sucedido
        if response['status'] == 'ok':
            file_link = response['data']['downloadPage']
            return f"Upload para GoFile concluído! Link para download: {file_link}"
        else:
            return f"Erro ao enviar o arquivo: {response.get('message', 'Erro desconhecido')}"
    except Exception as e:
        print(f"Erro ao fazer upload: {e}")
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

# Função para baixar o torrent usando libtorrent
def download_torrent(link):
    # Configurações do libtorrent
    ses = lt.session()
    ses.listen_on(6881, 6891)
    params = {
        'save_path': DOWNLOAD_PATH,
        'storage_mode': lt.storage_mode_t(2)
    }

    print("Adicionando o magnet link para download...")
    handle = lt.add_magnet_uri(ses, link, params)
    ses.start_dht()

    begin = time.time()
    print(datetime.datetime.now())

    print('Baixando Metadata...')
    while not handle.has_metadata():
        time.sleep(1)
    print('Metadata recebida, iniciando o download do torrent...')

    print("Iniciando", handle.name())

    while handle.status().state != lt.torrent_status.seeding:
        s = handle.status()
        state_str = ['queued', 'checking', 'downloading metadata',
                     'downloading', 'finished', 'seeding', 'allocating']
        print(f'{s.progress * 100:.2f}% completo (down: {s.download_rate / 1000:.1f} kb/s up: {s.upload_rate / 1000:.1f} kB/s peers: {s.num_peers}) {state_str[s.state]}')
        time.sleep(5)

    end = time.time()
    print(handle.name(), "COMPLETE")

    print("Tempo decorrido: ", int((end - begin) // 60), "min :", int((end - begin) % 60), "sec")
    print(datetime.datetime.now())

    return os.path.join(DOWNLOAD_PATH, handle.name())

# Comando para iniciar o download e o upload do torrent
async def start_download(update: Update, context: CallbackContext) -> None:
    if len(context.args) == 0:
        await update.message.reply_text("Por favor, forneça um link magnet ou um URL de arquivo torrent.")
        return
    
    link = context.args[0]

    try:
        file_path = download_torrent(link)
        if file_path:
            await update.message.reply_text(f'Baixando `{link}`... Monitorando progresso.')
            gofile_response = upload_file_gofile(file_path)
            if gofile_response:
                await update.message.reply_text(gofile_response)
                
                # Deletar arquivo após upload
                deletion_message = delete_local_file(file_path)
                await update.message.reply_text(deletion_message)
            else:
                await update.message.reply_text("Erro ao fazer upload do arquivo com GoFile.")
    except Exception as e:
        await update.message.reply_text(f"Erro ao adicionar o torrent: {e}")

# Função para mostrar o menu de instruções
async def show_menu(update: Update, context: CallbackContext) -> None:
    menu_message = (
        "Bem-vindo! Aqui estão os comandos disponíveis:\n\n"
        "/start_download <magnet_link ou .torrent URL> - Inicia o download a partir de um link magnet ou torrent.\n"
        "/help - Mostra este menu de ajuda.\n"
    )
    await update.message.reply_text(menu_message)

# Inicializar o bot com a nova forma de construção
application = Application.builder().token(bot_token).build()

# Configurar comandos do bot
application.add_handler(CommandHandler('start_download', start_download))
application.add_handler(CommandHandler('help', show_menu))

# Iniciar o bot
application.run_polling()
