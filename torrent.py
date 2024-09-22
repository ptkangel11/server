import os
import time
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import libtorrent as lt

# Configurações
bot_token = '7259838966:AAE69fL3BJKVXclATA8n6wYCKI0OmqStKrM'
DOWNLOAD_PATH = "./downloads/"

async def create_folder(parent_folder_id: str = None) -> str:
    """Cria uma pasta no GoFile para agrupar os uploads"""
    url = "https://api.gofile.io/contents/createFolder"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer KIxsOddlMz2Iy9Bbng0e3Yke2QsUEr3j'  # Substitua com seu token
    }

    json_data = {
        'folderName': 'UploadsTelegramBot'
    }
    parent_folder_id = '60447454-2e9a-4ecd-b990-f597ffb87e0c'
    if parent_folder_id:
        json_data['parentFolderId'] = parent_folder_id

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=json_data, headers=headers) as resp:
            response_json = await resp.json()
            if resp.status == 200 and 'data' in response_json:
                return response_json['data']['folderId']
            else:
                raise Exception(f"Erro ao criar pasta: {response_json}")

async def upload_file_to_folder(file_path: str, folder_id: str, update: Update) -> None:
    """Realiza o upload de um arquivo para uma pasta específica no GoFile"""
    try:
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
        form_data.add_field('folderId', folder_id)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as response:
                if response.status == 429:
                    await update.message.reply_text("Rate limit atingido. Esperando 60 segundos antes de tentar novamente...")
                    await asyncio.sleep(60)
                    return await upload_file_to_folder(file_path, folder_id, update)

                response_json = await response.json()
                if response_json and 'data' in response_json:
                    await update.message.reply_text(f"Upload de {file_path} concluído! Link: {response_json['data']['downloadPage']}")
                else:
                    await update.message.reply_text(f"Erro durante o upload de {file_path}.")
    except Exception as e:
        await update.message.reply_text(f"Erro durante o upload de {file_path}: {e}")

async def upload_directory(directory_path: str, update: Update) -> None:
    """Realiza o upload de todos os arquivos de um diretório para a mesma pasta no GoFile"""
    try:
        folder_id = await create_folder()
        await update.message.reply_text(f"Pasta criada no GoFile. Iniciando upload dos arquivos para a pasta.")

        for root, dirs, files in os.walk(directory_path):
            for file in files:
                full_path = os.path.join(root, file)
                await upload_file_to_folder(full_path, folder_id, update)

        await update.message.reply_text("Upload de todos os arquivos concluído!")
    except Exception as e:
        await update.message.reply_text(f"Erro durante o upload do diretório: {e}")

async def start_upload_directory(update: Update, context: CallbackContext) -> None:
    """Comando do bot para iniciar o upload de um diretório"""
    if len(context.args) == 0:
        await update.message.reply_text("Por favor, forneça o caminho de um diretório.")
        return
    
    directory_path = context.args[0]

    if os.path.isdir(directory_path):
        await update.message.reply_text(f"Iniciando upload do diretório {directory_path}.")
        await upload_directory(directory_path, update)
    else:
        await update.message.reply_text(f"O caminho {directory_path} não é um diretório válido.")

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
                    return servers[0]['name']
                else:
                    raise Exception("Nenhum servidor disponível.")
            else:
                raise Exception(f"Erro ao obter o servidor GoFile. Status Code: {resp.status}")

async def show_menu(update: Update, context: CallbackContext) -> None:
    menu_message = (
        "Bem-vindo! Aqui estão os comandos disponíveis:\n\n"
        "/start_upload_directory <diretório> - Faz upload de todos os arquivos de um diretório para o GoFile.\n"
        "/help - Mostra este menu de ajuda.\n"
    )
    await update.message.reply_text(menu_message)

# Configurando o bot
application = Application.builder().token(bot_token).build()

application.add_handler(CommandHandler('start_upload_directory', start_upload_directory))
application.add_handler(CommandHandler('help', show_menu))

if __name__ == '__main__':
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    application.run_polling()
