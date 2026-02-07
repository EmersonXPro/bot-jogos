import discord
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import asyncio
import concurrent.futures
import logging
from flask import Flask
from threading import Thread
import os

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GameBot')

# --- CONFIGURAÇÃO DO SERVIDOR WEB PARA O RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot está Online!"

def run_web_server():
    # O Render fornece a porta na variável de ambiente PORT
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()
# --------------------------------------------------

TOKEN = "MTQ2OTY0ODcxMTYyNDgyMjg3Nw.GXGtcp.5GnuMIU-BbUVrmQe-TFFZOBIAdY7iQRQ6EHv-I"

class GameBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = GameBot()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

def scrape_site(base_url, query):
    try:
        search_url = f"{base_url}/?s={query.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        first_result = soup.select_one('h2.post-title a, h2.entry-title a, div.post-details h2 a, article h2 a')
        if not first_result:
            link_tag = soup.find('a', string=re.compile(re.escape(query), re.I))
            if link_tag: first_result = link_tag
            else: return None
            
        game_url = urljoin(base_url, first_result['href'])
        game_page = requests.get(game_url, headers=headers, timeout=10)
        game_soup = BeautifulSoup(game_page.text, 'html.parser')
        
        title = game_soup.find('h1').get_text().strip() if game_soup.find('h1') else first_result.get_text().strip()
        
        size = "Não informado"
        content_text = game_soup.get_text()
        size_match = re.search(r'(?:Size|Tamanho):\s*([\d.]+\s*(?:GB|MB|KB))', content_text, re.I)
        if size_match: size = size_match.group(1)
        
        links = []
        domains = ['buzzheavier.com', 'filecrypt.cc', 'megaup.net', 'gofile.io', 'pixeldrain.com', '1fichier.com', 'qiwi.gg']
        all_links = game_soup.find_all('a', href=True)
        for a in all_links:
            href = a['href']
            if any(domain in href.lower() for domain in domains):
                if href.startswith('//'): href = 'https:' + href
                if href not in links: links.append(href)
        
        img_url = None
        og_image = game_soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
        
        if not img_url:
            img_tag = game_soup.select_one('div.entry-content img, img.wp-post-image, article img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src and not src.startswith('data:'):
                    img_url = urljoin(game_url, src)
        
        if img_url:
            img_url = re.sub(r'-\d+x\d+\.(jpg|jpeg|png|webp)$', r'.\1', img_url)
        
        return {
            "name": title,
            "size": size,
            "primary_link": links[0] if len(links) > 0 else "N/A",
            "secondary_link": links[1] if len(links) > 1 else "N/A",
            "image": img_url
        }
    except Exception as e:
        logger.error(f"Erro em {base_url}: {e}")
        return None

def do_full_search(nome):
    sites = ["https://steamrip.com", "https://repack-games.com", "https://ankergames.net"]
    for site in sites:
        res = scrape_site(site, nome)
        if res: return res
    return None

@client.tree.command(name="jogos", description="Busca links de download para um jogo")
async def jogos(interaction: discord.Interaction, nome: str):
    await interaction.response.send_message(f"🔍 Buscando **{nome}** nos sites de jogos... Por favor, aguarde.")
    
    async def run_search():
        try:
            loop = asyncio.get_running_loop()
            game_info = await loop.run_in_executor(executor, do_full_search, nome)
            
            if not game_info:
                await interaction.edit_original_response(content=f"❌ Jogo **{nome}** não encontrado.")
                return

            response_text = (
                f"**Nome do jogo:** {game_info['name']}\n\n"
                f"**Tamanho:** {game_info['size']}\n\n"
                f"**Link Primário:** {game_info['primary_link']}\n"
                f"**Link secundário:** {game_info['secondary_link']}\n\n"
                f"**Método de Instalação:**\n"
                f"    Após baixar o arquivo do jogo através dos links acima, em seu PC extraia o arquivo usando um gerenciador de arquivos, recomendo o WinRAR. Dentro da pasta do jogo, Procurar o Executável do Jogo que geralmente é o nome do jogo com .Exe no final, execute como Administrador - Pronto, seja feliz."
            )
            
            embed = discord.Embed(description=response_text, color=discord.Color.blue())
            if game_info['image']:
                embed.set_image(url=game_info['image'])
            
            await interaction.edit_original_response(content=None, embed=embed)
        except Exception as e:
            logger.error(f"Erro: {e}")
            try: await interaction.edit_original_response(content="⚠️ Erro ao buscar o jogo.")
            except: pass

    asyncio.create_task(run_search())

@client.event
async def on_ready():
    logger.info(f'BOT ONLINE: {client.user}')

if __name__ == "__main__":
    # Inicia o servidor web para o Render não derrubar o bot
    keep_alive()
    # Inicia o bot
    client.run(TOKEN)
