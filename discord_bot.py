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
        
        # Tenta encontrar o tamanho
        size = "Não especificado"
        content_text = game_soup.get_text()
        size_match = re.search(r'Size:\s*([\d.]+\s*(?:GB|MB|KB))', content_text, re.I)
        if size_match:
            size = size_match.group(1)
        
        # Links de download
        links = []
        for a in game_soup.find_all('a', href=True):
            if any(x in a['href'].lower() for x in ['download', 'drive', 'mega', 'mediafire', 'torrent']):
                if a['href'].startswith('http'):
                    links.append(f"[{a.get_text().strip() or 'Link'}]({a['href']})")
        
        # Instruções
        instructions = "1. Extraia os arquivos\n2. Monte a ISO se necessário\n3. Instale o jogo\n4. Copie o crack se houver"
        
        # Imagem
        img_tag = game_soup.find('img', class_=re.compile(r'wp-post-image|featured'))
        image_url = img_tag['src'] if img_tag else None
        
        return {
            'title': title,
            'size': size,
            'links': "\n".join(links[:3]) if links else "Links não encontrados diretamente.",
            'instructions': instructions,
            'image': image_url
        }
    except Exception as e:
        logger.error(f"Erro ao raspar {base_url}: {e}")
        return None

@client.tree.command(name="jogos", description="Busca links de download para um jogo")
async def jogos(interaction: discord.Interaction, nome: str):
    await interaction.response.defer()
    
    sites = [
        "https://repack-games.com",
        "https://ankergames.net",
        "https://steamrip.com"
    ]
    
    found_game = None
    for site in sites:
        result = await asyncio.get_event_loop().run_in_executor(executor, scrape_site, site, nome)
        if result:
            found_game = result
            break
            
    if found_game:
        embed = discord.Embed(title=found_game['title'], color=discord.Color.blue())
        embed.add_field(name="📦 Tamanho", value=found_game['size'], inline=True)
        embed.add_field(name="🔗 Links de Download", value=found_game['links'], inline=False)
        embed.add_field(name="🛠️ Instruções", value=found_game['instructions'], inline=False)
        if found_game['image']:
            embed.set_image(url=found_game['image'])
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Desculpe, não encontrei o jogo '{nome}' nos sites monitorados.")

@client.event
async def on_ready():
    logger.info(f'Bot logado como {client.user}')
    print(f'Bot logado como {client.user}')

if __name__ == "__main__":
    keep_alive()
    client.run(TOKEN)
