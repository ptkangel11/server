import os
import time
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import libtorrent as lt
import logging

# Configurações
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'
DOWNLOAD_PATH = "./downloads/"
GOFILE_API_TOKEN = 'KIxsOddlMz2Iy9Bbng0e3Yke2QsUEr3j'
PARENT_FOLDER_ID = '60447454-2e9a-4ecd-b990-f597ffb87e0c'

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_folder(parent_folder_id: str = None) -> str:
    """Cria uma pasta no GoFile para agrupar os uploads."""
    url = "https://api.gofile.io/contents/createFolder"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GOFILE_API_TOKEN}'
    }

    json_data = {
        'parentFolderId': PARENT_FOLDER_ID,
        'folderName': 'UploadsTelegramBot'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=json_data, headers=headers) as resp:
            response_json = await resp.json()
            logger.info(f"Create folder response: {response_json}")
            if resp.status == 200 and response_json.get('status') == 'ok':
                folder_id = response_json.get('data', {}).get('folderId')
                if folder_id:
                    return folder_id
                else:
                    error_message = f"Folder ID não encontrado na resposta: {response_json}"
                    logger.error(error_message)
                    raise Exception(error_message)
            else:
                error_message = f"Erro ao criar pasta: {response_json}"
                logger.error(error_message)
                raise Exception(error_message)

async def upload_file_to_folder(file_path: str, folder_id: str, update: Update) -> None:
    """Realiza o upload de um arquivo para uma pasta específica no GoFile."""
    try:
        server = await get_server()
        url = f"https://{server}.gofile.io/contents/uploadFile"

        form_data = aiohttp.FormData()
        form_data.add_field(
            'file',
            open(file_path, 'rb'),
            filename=os.path.basename(file_path),
            content_type='application/octet-stream'
        )
        form_data.add_field('folderId', folder_id)
        form_data.add_field('token', GOFILE_API_TOKEN)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as response:
                if response.status == 429:
                    await update.message.reply_text("Rate limit atingido. Esperando 60 segundos antes de tentar novamente...")
                    await asyncio.sleep(60)
                    return await upload_file_to_folder(file_path, folder_id, update)

                response_json = await response.json()
                logger.info(f"Upload response: {response_json}")
                if response_json and 'data' in response_json:
                    await update.message.reply_text(f"Upload de {file_path} concluído! Link: {response_json['data']['downloadPage']}")
                else:
                    error_message = f"Erro durante o upload de {file_path}."
                    logger.error(error_message)
                    await update.message.reply_text(error_message)
    except Exception as e:
        error_message = f"Erro durante o upload de {file_path}: {e}"
        logger.error(error_message)
        await update.message.reply_text(error_message)

async def upload_directory(directory_path: str, folder_id: str, update: Update) -> None:
    """Realiza o upload de todos os arquivos de um diretório para a mesma pasta no GoFile."""
    try:
        await update.message.reply_text(f"Iniciando upload dos arquivos para a pasta {folder_id}.")

        for root, dirs, files in os.walk(directory_path):
            for file in files:
                full_path = os.path.join(root, file)
                await upload_file_to_folder(full_path, folder_id, update)

        await update.message.reply_text("Upload de todos os arquivos concluído!")
    except Exception as e:
        error_message = f"Erro durante o upload do diretório: {e}"
        logger.error(error_message)
        await update.message.reply_text(error_message)

async def download_torrent(link: str, update: Update) -> str:
    """Faz o download de um torrent a partir de um link."""
    try:
        logger.info(f"Iniciando download do torrent: {link}")
        ses = lt.session()
        ses.listen_on(6881, 6891)
        params = {
            'save_path': DOWNLOAD_PATH,
            'storage_mode': lt.storage_mode_t.storage_mode_sparse
        }

        logger.info("Adicionando magnet link")
        handle = lt.add_magnet_uri(ses, link, params)
        ses.start_dht()

        logger.info("Aguardando metadata")
        begin = time.time()
        status_message = await update.message.reply_text("Iniciando download do torrent...")

        while not handle.has_metadata():
            await asyncio.sleep(1)
            await status_message.edit_text("Baixando metadata...")

        logger.info("Metadata recebida, iniciando download")
        while handle.status().state != lt.torrent_status.seeding:
            s = handle.status()
            state_str = ['queued', 'checking', 'downloading metadata',
                         'downloading', 'finished', 'seeding', 'allocating']
            status_text = (
                f"Nome: {handle.name()}\n"
                f"Status: {state_str[s.state]}\n"
                f"Progresso: {s.progress * 100:.2f}%\n"
                f"Download: {s.download_rate / 1000:.1f} kB/s\n"
                f"Upload: {s.upload_rate / 1000:.1f} kB/s\n"
                f"Peers: {s.num_peers}"
            )
            logger.info(status_text)
            await status_message.edit_text(status_text)
            await asyncio.sleep(5)

        end = time.time()
        elapsed_time = int(end - begin)
        final_status = (
            f"Download completo: {handle.name()}\n"
            f"Tempo total: {elapsed_time // 60} min : {elapsed_time % 60} sec"
        )
        logger.info(final_status)
        await status_message.edit_text(final_status)

        return os.path.join(DOWNLOAD_PATH, handle.name())
    except Exception as e:
        error_message = f"Erro durante o download do torrent: {str(e)}"
        logger.error(error_message, exc_info=True)
        await update.message.reply_text(error_message)
        return None

async def start_download(update: Update, context: CallbackContext) -> None:
    """Inicia o download e upload do torrent."""
    if len(context.args) == 0:
        await update.message.reply_text("Por favor, forneça um link magnet ou um URL de arquivo torrent.")
        return
    
    link = context.args[0]

    try:
        file_path = await download_torrent(link, update)
        if file_path:
            await update.message.reply_text(f'Download concluído. Criando pasta no GoFile...')
            folder_id = await create_folder()
            logger.info(f"Folder created with ID: {folder_id}")
            if folder_id:
                await upload_directory(os.path.dirname(file_path), folder_id, update)
            else:
                error_message = "Erro ao criar a pasta no GoFile."
                logger.error(error_message)
                await update.message.reply_text(error_message)
        else:
            error_message = "Erro ao baixar o arquivo torrent."
            logger.error(error_message)
            await update.message.reply_text(error_message)
    except Exception as e:
        error_message = f"Erro ao processar o torrent: {str(e)}"
        logger.error(error_message, exc_info=True)
        await update.message.reply_text(error_message)
        
async def get_server() -> str:
    """Obtém um servidor disponível do GoFile."""
    url = "https://api.gofile.io/servers"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 429:
                raise Exception("Rate limit atingido. Tentando novamente após 60 segundos...")
            if resp.status == 200:
                server_data = await resp.json()
                logger.info(f"Server data: {server_data}")
                servers = server_data['data']['servers']
                if servers:
                    return servers[0]['name']
                else:
                    raise Exception("Nenhum servidor disponível.")
            else:
                raise Exception(f"Erro ao obter o servidor GoFile. Status Code: {resp.status}")

async def show_menu(update: Update, context: CallbackContext) -> None:
    """Exibe o menu de comandos do bot."""
    menu_message = (
        "Bem-vindo! Aqui estão os comandos disponíveis:\n\n"
        "/start_download <magnet_link ou .torrent URL> - Inicia o download a partir de um link magnet ou torrent e faz upload para GoFile.\n"
        "/help - Mostra este menu de ajuda.\n"
    )
    await update.message.reply_text(menu_message)

# Configurando o bot
application = Application.builder().token(bot_token).build()

application.add_handler(CommandHandler('start_download', start_download))
application.add_handler(CommandHandler('help', show_menu))

if __name__ == '__main__':
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    application.run_polling()
