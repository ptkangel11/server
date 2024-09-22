import os
import time
import asyncio
import libtorrent as lt
import aiohttp
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from requests_toolbelt.multipart.encoder import MultipartEncoder

# Configurações
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'
DOWNLOAD_PATH = "./downloads/"

async def encode_file(file_path: str) -> MultipartEncoder:
    """Cria o arquivo multipart para upload"""
    return MultipartEncoder(fields={'file': (os.path.basename(file_path), open(file_path, 'rb'), 'application/octet-stream')})

async def get_server() -> str:
    """Obtém o servidor disponível do GoFile para upload"""
    url = "https://api.gofile.io/servers"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 429:
                raise Exception("Rate limit atingido. Tentando novamente após 60 segundos...")
            if resp.status == 200:
                server_data = await resp.json()
                servers = server_data['data']['servers']
                if servers:
                    return servers[0]['name']  # Retorna o primeiro servidor disponível
                else:
                    raise Exception("Nenhum servidor disponível.")
            else:
                raise Exception(f"Erro ao obter o servidor GoFile. Status Code: {resp.status}")

def zip_folder(folder_path: str) -> str:
    """Compacta uma pasta e retorna o caminho do arquivo zip"""
    output_zip = os.path.join(DOWNLOAD_PATH, os.path.basename(folder_path) + '.zip')
    shutil.make_archive(output_zip.replace('.zip', ''), 'zip', folder_path)
    return output_zip

async def upload_file(file_path: str, update: Update) -> None:
    """Realiza o upload de um arquivo para GoFile"""
    try:
        # Se for um diretório, compactar
        if os.path.isdir(file_path):
            await update.message.reply_text(f"O caminho {file_path} é um diretório. Compactando...")
            file_path = zip_folder(file_path)
            await update.message.reply_text(f"Diretório compactado: {file_path}")

        # Obter servidor GoFile
        server = await get_server()
        url = f"https://{server}.gofile.io/uploadFile"

        # Criar FormData para envio correto com aiohttp
        form_data = aiohttp.FormData()
        form_data.add_field(
            'file',
            open(file_path, 'rb'),
            filename=os.path.basename(file_path),
            content_type='application/octet-stream'
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as response:
                if response.status == 429:
                    await update.message.reply_text("Rate limit atingido. Esperando 60 segundos antes de tentar novamente...")
                    await asyncio.sleep(60)  # Espera 60 segundos antes de tentar novamente
                    return await upload_file(file_path, update)

                response_json = await response.json()
                if response_json and 'data' in response_json:
                    await update.message.reply_text(f"Upload concluído com sucesso! Link: {response_json['data']['downloadPage']}")
                else:
                    await update.message.reply_text("Erro durante o upload.")
    except Exception as e:
        await update.message.reply_text(f"Erro durante o upload: {e}")

def parallel_upload(file_path, update):
    """Executa o upload de arquivo em segundo plano"""
    loop = asyncio.get_event_loop()
    loop.create_task(upload_file(file_path, update))

async def download_torrent(link, update: Update, context: CallbackContext):
    """Faz o download de um torrent a partir de um link magnet ou URL"""
    ses = lt.session()
    ses.listen_on(6881, 6891)
    params = {
        'save_path': DOWNLOAD_PATH,
        'storage_mode': lt.storage_mode_t(2)
    }

    handle = lt.add_magnet_uri(ses, link, params)
    ses.start_dht()

    begin = time.time()
    status_message = await update.message.reply_text("Iniciando download do torrent...")

    while not handle.has_metadata():
        await asyncio.sleep(1)
        await status_message.edit_text("Baixando metadata...")

    print("Iniciando", handle.name())

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
        await status_message.edit_text(status_text)
        await asyncio.sleep(5)

    end = time.time()
    elapsed_time = int(end - begin)
    final_status = (
        f"Download completo: {handle.name()}\n"
        f"Tempo total: {elapsed_time // 60} min : {elapsed_time % 60} sec"
    )
    await status_message.edit_text(final_status)

    return os.path.join(DOWNLOAD_PATH, handle.name())

async def start_download(update: Update, context: CallbackContext) -> None:
    """Inicia o processo de download e upload de um torrent"""
    if len(context.args) == 0:
        await update.message.reply_text("Por favor, forneça um link magnet ou um URL de arquivo torrent.")
        return
    
    link = context.args[0]

    try:
        file_path = await download_torrent(link, update, context)
        if file_path:
            await update.message.reply_text(f'Download concluído. Iniciando upload para GoFile...')
            parallel_upload(file_path, update)  # Passa update aqui
            await update.message.reply_text("Upload iniciado em paralelo. Aguarde o processo ser concluído.")
        else:
            await update.message.reply_text("Erro ao baixar o arquivo torrent.")
    except Exception as e:
        await update.message.reply_text(f"Erro ao processar o torrent: {e}")

async def show_menu(update: Update, context: CallbackContext) -> None:
    """Exibe o menu de ajuda"""
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
    # Criando diretório de download se não existir
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    application.run_polling()
