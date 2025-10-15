from flask import Flask, request, jsonify, render_template_string
import requests
import re
from difflib import get_close_matches
import numpy as np
from datetime import datetime

# ==============================
# CONFIGURAÇÕES
# ==============================
OPENROVER_API_KEY = "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"
MODEL_ANA_ESTER = "deepseek/deepseek-r1-distill-llama-70b:free"
app = Flask(__name__)

# ==============================
# CONFIGURAÇÕES DE INTEGRAÇÃO WORDPRESS (NOVO)
# ==============================
WORDPRESS_API_BASE = "https://chemteqsolutions.com/wp-json/chemteq/v1/lab"

def verificar_usuario_wordpress(user_id, user_email):
    """
    Verifica se o usuário é válido no WordPress
    """
    try:
        url = f"{WORDPRESS_API_BASE}/verify-user"
        params = {
            'user_id': user_id,
            'user_email': user_email
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('valid', False), data.get('user', {})
        
        return False, {}
    except Exception as e:
        print(f"Erro na verificação WordPress: {e}")
        return False, {}

def obter_plano_usuario(user_id):
    """
    Obtém o plano do usuário no WordPress
    """
    try:
        url = f"{WORDPRESS_API_BASE}/user-plan"
        params = {'user_id': user_id}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('plan', 'free')
        
        return 'free'
    except:
        return 'free'

# ==============================
# SISTEMA DE AUTENTICAÇÃO (NOVO)
# ==============================
def criar_usuario_wordpress(email, senha, nome):
    """
    Cria um novo usuário no WordPress
    """
    try:
        url = f"{WORDPRESS_API_BASE}/register-user"
        data = {
            'user_email': email,
            'user_password': senha,
            'user_name': nome
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('success', False), data.get('user_id', ''), data.get('message', '')
        
        return False, '', 'Erro na comunicação com o servidor'
    except Exception as e:
        print(f"Erro no cadastro WordPress: {e}")
        return False, '', 'Erro de conexão'

def autenticar_usuario_wordpress(email, senha):
    """
    Autentica usuário no WordPress
    """
    try:
        url = f"{WORDPRESS_API_BASE}/login-user"
        data = {
            'user_email': email,
            'user_password': senha
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('success', False), data.get('user', {}), data.get('message', '')
        
        return False, {}, 'Erro na comunicação com o servidor'
    except Exception as e:
        print(f"Erro no login WordPress: {e}")
        return False, {}, 'Erro de conexão'

# ==============================
# NOVAS ROTAS DE AUTENTICAÇÃO
# ==============================


@app.route('/login', methods=['POST'])
def login_user():
    """Autentica um usuário"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email e senha são obrigatórios'})
        
        # Integração com WordPress
        success, user_data, message = autenticar_usuario_wordpress(email, password)
        
        if success:
            user_plan = user_data.get('plan', 'free')
            return jsonify({
                'success': True,
                'message': 'Login realizado com sucesso!',
                'user_id': user_data.get('id', ''),
                'user_name': user_data.get('name', 'Usuário'),
                'plan': user_plan,
                'limits': laboratorio.gerenciador_planos.limites.get(user_plan, laboratorio.gerenciador_planos.limites['free']),
                'redirect_url': 'https://chemteqsolutions.com/laboratorio'  # ✅ ADD REDIRECT URL
            })
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro no login: {str(e)}'})
# ==============================
# SISTEMA DE PLANOS E LIMITES (NOVO)
# ==============================
class GerenciadorPlanos:
    def __init__(self):
        self.limites = {
            'free': {
                'compostos_por_analise': 5,
                'analises_dia': 10,
                'acesso_ia': True,
                'export_relatorios': False
            },
            'premium': {
                'compostos_por_analise': 20,
                'analises_dia': 100,
                'acesso_ia': True,
                'export_relatorios': True
            },
            'enterprise': {
                'compostos_por_analise': 100,
                'analises_dia': 1000,
                'acesso_ia': True,
                'export_relatorios': True
            },
             'guest': { 
                'compostos_por_analise': 3,
                'analises_dia': 5,
                'acesso_ia': False,
                'export_relatorios': False
            },
        }
    
    def verificar_limite_compostos(self, plano, num_compostos):
        limite = self.limites.get(plano, self.limites['free'])
        return num_compostos <= limite['compostos_por_analise']
    
    def pode_usar_ia(self, plano):
        limite = self.limites.get(plano, self.limites['free'])
        return limite['acesso_ia']

# ==============================
# BASE DE DADOS DE COMPOSTOS (MANTIDO ORIGINAL - 100+ LINHAS)
# ==============================
COMPOSTOS_BASE = {
    'water': {
        'formula': 'H₂O', 'peso_molecular': 18.02, 'logp': -1.38,
        'grupos_funcionais': ['Água', 'Solvente Polar', 'Hidroxila'],
        'tipo': 'polar', 'descricao': 'Solvente universal polar',
        'pubchem_cid': '962', 'cas': '7732-18-5',
        'sinonimos': ['água', 'h2o', 'water', 'aqua'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/962'
    },
    'ethanol': {
        'formula': 'C₂H₆O', 'peso_molecular': 46.07, 'logp': -0.31,
        'grupos_funcionais': ['Álcool', 'Hidroxila', 'Polar'],
        'tipo': 'polar', 'descricao': 'Álcool solvente polar',
        'pubchem_cid': '702', 'cas': '64-17-5',
        'sinonimos': ['etanol', 'ethanol', 'alcohol', 'ethyl alcohol', 'grains alcohol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/702'
    },
    'methanol': {
        'formula': 'CH₄O', 'peso_molecular': 32.04, 'logp': -0.77,
        'grupos_funcionais': ['Álcool', 'Hidroxila', 'Polar'],
        'tipo': 'polar', 'descricao': 'Álcool metílico solvente',
        'pubchem_cid': '887', 'cas': '67-56-1',
        'sinonimos': ['metanol', 'methanol', 'methyl alcohol', 'wood alcohol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/887'
    },
    'hexane': {
        'formula': 'C₆H₁₄', 'peso_molecular': 86.18, 'logp': 3.90,
        'grupos_funcionais': ['Alcano', 'Cadeia Longa', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Solvente orgânico apolar',
        'pubchem_cid': '8058', 'cas': '110-54-3',
        'sinonimos': ['hexano', 'hexane', 'n-hexane'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/8058'
    },
    'acetone': {
        'formula': 'C₃H₆O', 'peso_molecular': 58.08, 'logp': -0.24,
        'grupos_funcionais': ['Cetona', 'Polar'],
        'tipo': 'polar', 'descricao': 'Solvente cetônico polar',
        'pubchem_cid': '180', 'cas': '67-64-1',
        'sinonimos': ['acetona', 'acetone', 'propanone', 'dimethyl ketone'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/180'
    },
    'chloroform': {
        'formula': 'CHCl₃', 'peso_molecular': 119.38, 'logp': 1.97,
        'grupos_funcionais': ['Halogenado', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Solvente halogenado',
        'pubchem_cid': '6212', 'cas': '67-66-3',
        'sinonimos': ['clorofórmio', 'chloroform', 'trichloromethane'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/6212'
    },
    'glycerol': {
        'formula': 'C₃H₈O₃', 'peso_molecular': 92.09, 'logp': -1.76,
        'grupos_funcionais': ['Poliálcool', 'Hidroxila', 'Polar'],
        'tipo': 'polar', 'descricao': 'Poliálcool viscoso',
        'pubchem_cid': '753', 'cas': '56-81-5',
        'sinonimos': ['glicerol', 'glycerol', 'glycerin', 'glycerine', 'propane-1,2,3-triol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/753'
    },
    'sodium dodecyl sulfate': {
        'formula': 'C₁₂H₂₅NaO₄S', 'peso_molecular': 288.38, 'logp': 1.60,
        'grupos_funcionais': ['Surfactante', 'Sulfato', 'Aniônico'],
        'tipo': 'surfactante', 'descricao': 'Surfactante aniônico',
        'pubchem_cid': '3423265', 'cas': '151-21-3',
        'sinonimos': ['sds', 'sodium lauryl sulfate', 'sls', 'dodecyl sulfate sodium'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/3423265'
    },
    'sds': {
        'formula': 'C₁₂H₂₅NaO₄S', 'peso_molecular': 288.38, 'logp': 1.60,
        'grupos_funcionais': ['Surfactante', 'Sulfato', 'Aniônico'],
        'tipo': 'surfactante', 'descricao': 'Surfactante aniônico (abreviação)',
        'pubchem_cid': '3423265', 'cas': '151-21-3',
        'sinonimos': ['sodium dodecyl sulfate', 'sodium lauryl sulfate', 'sls'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/3423265'
    },
    'oil': {
        'formula': 'Variável', 'peso_molecular': 280.45, 'logp': 8.50,
        'grupos_funcionais': ['Lipídio', 'Apolar', 'Cadeia Longa'],
        'tipo': 'apolar', 'descricao': 'Óleo vegetal/apolar',
        'pubchem_cid': '', 'cas': '',
        'sinonimos': ['óleo', 'oil', 'vegetable oil', 'mineral oil'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov'
    },
    'benzene': {
        'formula': 'C₆H₆', 'peso_molecular': 78.11, 'logp': 2.13,
        'grupos_funcionais': ['Aromático', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Hidrocarboneto aromático',
        'pubchem_cid': '241', 'cas': '71-43-2',
        'sinonimos': ['benzeno', 'benzene', 'benzol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/241'
    },
    'toluene': {
        'formula': 'C₇H₈', 'peso_molecular': 92.14, 'logp': 2.73,
        'grupos_funcionais': ['Aromático', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Derivado aromático do benzeno',
        'pubchem_cid': '1140', 'cas': '108-88-3',
        'sinonimos': ['tolueno', 'toluene', 'methylbenzene', 'phenylmethane'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/1140'
    },
    'acetic acid': {
        'formula': 'C₂H₄O₂', 'peso_molecular': 60.05, 'logp': 0.23,
        'grupos_funcionais': ['Ácido Carboxílico', 'Polar'],
        'tipo': 'polar', 'descricao': 'Ácido acético',
        'pubchem_cid': '176', 'cas': '64-19-7',
        'sinonimos': ['ácido acético', 'acetic acid', 'ethanoic acid', 'vinegar acid'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/176'
    },
    'diethyl ether': {
        'formula': 'C₄H₁₀O', 'peso_molecular': 74.12, 'logp': 0.89,
        'grupos_funcionais': ['Éter', 'Polaridade Moderada'],
        'tipo': 'apolar', 'descricao': 'Éter dietílico solvente',
        'pubchem_cid': '3283', 'cas': '60-29-7',
        'sinonimos': ['éter dietílico', 'diethyl ether', 'ether', 'ethyl ether', 'ethoxyethane'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/3283'
    },
    'benzophenone-3': {
        'formula': 'C₁₄H₁₂O₃', 'peso_molecular': 228.24, 'logp': 3.50,
        'grupos_funcionais': ['Benzofenona', 'Protetor Solar', 'Aromático'],
        'tipo': 'apolar', 'descricao': 'Filtro UV orgânico',
        'pubchem_cid': '4632', 'cas': '131-57-7',
        'sinonimos': ['oxybenzone', 'benzophenone-3', '2-hydroxy-4-methoxybenzophenone'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/4632'
    },
    'sodium chloride': {
        'formula': 'NaCl', 'peso_molecular': 58.44, 'logp': -4.00,
        'grupos_funcionais': ['Sal', 'Iônico', 'Eletrólito'],
        'tipo': 'polar', 'descricao': 'Cloreto de sódio',
        'pubchem_cid': '5234', 'cas': '7647-14-5',
        'sinonimos': ['nacl', 'salt', 'table salt', 'halite'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/5234'
    },
    'propylene glycol': {
        'formula': 'C₃H₈O₂', 'peso_molecular': 76.09, 'logp': -0.92,
        'grupos_funcionais': ['Diol', 'Polar', 'Umectante'],
        'tipo': 'polar', 'descricao': 'Solvente e umectante',
        'pubchem_cid': '1030', 'cas': '57-55-6',
        'sinonimos': ['propilenoglicol', 'propylene glycol', '1,2-propanediol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/1030'
    },
    'sodium laureth sulfate': {
        'formula': 'C₁₂H₂₅NaO₄S', 'peso_molecular': 288.38, 'logp': 1.20,
        'grupos_funcionais': ['Surfactante', 'Sulfato', 'Aniônico', 'Etoxilado'],
        'tipo': 'surfactante', 'descricao': 'Surfactante aniônico etoxilado',
        'pubchem_cid': '23665879', 'cas': '25155-30-0',
        'sinonimos': ['sles', 'sodium laureth sulfate', 'sodium lauryl ether sulfate'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/23665879'
    },
    'triclosan': {
        'formula': 'C₁₂H₇Cl₃O₂', 'peso_molecular': 289.54, 'logp': 4.76,
        'grupos_funcionais': ['Antibacteriano', 'Fenol', 'Clorado'],
        'tipo': 'apolar', 'descricao': 'Agente antibacteriano e antifúngico',
        'pubchem_cid': '5564', 'cas': '3380-34-5',
        'sinonimos': ['triclosan', '2,4,4-trichloro-2-hydroxydiphenyl ether'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/5564'
    },
    'citric acid': {
        'formula': 'C₆H₈O₇', 'peso_molecular': 192.12, 'logp': -1.72,
        'grupos_funcionais': ['Ácido Carboxílico', 'Ácido Orgânico', 'Polar'],
        'tipo': 'polar', 'descricao': 'Ácido cítrico - acidulante natural',
        'pubchem_cid': '311', 'cas': '77-92-9',
        'sinonimos': ['ácido cítrico', 'citric acid', '2-hydroxy-1,2,3-propanetricarboxylic acid'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/311'
    },
    'methylparaben': {
        'formula': 'C₈H₈O₃', 'peso_molecular': 152.15, 'logp': 1.96,
        'grupos_funcionais': ['Parabeno', 'Conservante', 'Éster'],
        'tipo': 'apolar', 'descricao': 'Conservante sintético',
        'pubchem_cid': '7456', 'cas': '99-76-3',
        'sinonimos': ['methylparaben', 'methyl paraben', 'methyl 4-hydroxybenzoate'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/7456'
    },
    'glycerin': {
        'formula': 'C₃H₈O₃', 'peso_molecular': 92.09, 'logp': -1.76,
        'grupos_funcionais': ['Poliálcool', 'Hidroxila', 'Polar'],
        'tipo': 'polar', 'descricao': 'Umectante e solvente',
        'pubchem_cid': '753', 'cas': '56-81-5',
        'sinonimos': ['glicerina', 'glycerin', 'glycerol', 'glycerine'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/753'
    },
    'cetearyl alcohol': {
        'formula': 'C₃₄H₇₂O₂', 'peso_molecular': 512.94, 'logp': 12.50,
        'grupos_funcionais': ['Álcool Graxo', 'Emulsificante', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Álcool graxo emulsificante',
        'pubchem_cid': '5283665', 'cas': '67762-27-0',
        'sinonimos': ['cetearyl alcohol', 'cetylstearyl alcohol'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/5283665'
    },
    'dimethicone': {
        'formula': 'C₆H₁₈OSi₂', 'peso_molecular': 162.38, 'logp': 4.20,
        'grupos_funcionais': ['Silicona', 'Emoliente', 'Apolar'],
        'tipo': 'apolar', 'descricao': 'Silicona emoliente',
        'pubchem_cid': '63032', 'cas': '9006-65-9',
        'sinonimos': ['dimethicone', 'polydimethylsiloxane'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/63032'
    },
    # =============== COMPOSTOS REATIVOS ADICIONADOS ===============
    'sodium metal': {
        'formula': 'Na', 'peso_molecular': 22.99, 'logp': None,
        'grupos_funcionais': ['Metal Alcalino', 'Redutor Forte'],
        'tipo': 'reativo', 'descricao': 'Metal alcalino altamente reativo',
        'pubchem_cid': '5742488', 'cas': '7440-23-5',
        'sinonimos': ['sódio metálico', 'sodium', 'na metal', 'metallic sodium'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/5742488'
    },
    'potassium metal': {
        'formula': 'K', 'peso_molecular': 39.10, 'logp': None,
        'grupos_funcionais': ['Metal Alcalino', 'Redutor Forte'],
        'tipo': 'reativo', 'descricao': 'Metal alcalino ainda mais reativo que sódio',
        'pubchem_cid': '5462270', 'cas': '7440-09-7',
        'sinonimos': ['potássio metálico', 'potassium', 'k metal'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/5462270'
    },
    'acetyl chloride': {
        'formula': 'C₂H₃ClO', 'peso_molecular': 78.50, 'logp': 0.70,
        'grupos_funcionais': ['Cloreto de Ácido', 'Halogenado', 'Eletrofílico'],
        'tipo': 'reativo', 'descricao': 'Cloreto de acetila - reage violentamente com água',
        'pubchem_cid': '6618', 'cas': '75-36-5',
        'sinonimos': ['acetyl chloride', 'ethanoyl chloride', 'cloreto de acetila'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/6618'
    },
    'thionyl chloride': {
        'formula': 'SOCl₂', 'peso_molecular': 118.97, 'logp': 1.20,
        'grupos_funcionais': ['Cloreto de Sulfurila', 'Reagente de Cloração'],
        'tipo': 'reativo', 'descricao': 'Reage violentamente com água, liberando SO₂ e HCl',
        'pubchem_cid': '24385', 'cas': '7719-09-7',
        'sinonimos': ['thionyl chloride', 'cloreto de sulfurila'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/24385'
    },
    'hydrogen peroxide': {
        'formula': 'H₂O₂', 'peso_molecular': 34.01, 'logp': -1.40,
        'grupos_funcionais': ['Peróxido', 'Oxidante Forte'],
        'tipo': 'reativo', 'descricao': 'Agente oxidante forte',
        'pubchem_cid': '784', 'cas': '7722-84-1',
        'sinonimos': ['peróxido de hidrogênio', 'hydrogen peroxide', 'agua oxigenada'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/784'
    },
    'sodium hydroxide': {
        'formula': 'NaOH', 'peso_molecular': 40.00, 'logp': -2.00,
        'grupos_funcionais': ['Base Forte', 'Hidróxido', 'Corrosivo'],
        'tipo': 'reativo', 'descricao': 'Base forte corrosiva',
        'pubchem_cid': '14798', 'cas': '1310-73-2',
        'sinonimos': ['hidróxido de sódio', 'sodium hydroxide', 'soda cáustica'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/14798'
    },
    'hydrochloric acid': {
        'formula': 'HCl', 'peso_molecular': 36.46, 'logp': -1.10,
        'grupos_funcionais': ['Ácido Forte', 'Corrosivo'],
        'tipo': 'reativo', 'descricao': 'Ácido forte corrosivo',
        'pubchem_cid': '313', 'cas': '7647-01-0',
        'sinonimos': ['ácido clorídrico', 'hydrochloric acid', 'hcl'],
        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/313'
    }
}

# ==============================
# SISTEMA DE DETECÇÃO DE PERIGOS IMEDIATOS (MANTIDO ORIGINAL)
# ==============================
def _avaliar_perigos_imediatos(dados_compostos):
    """
    Detecta combinações quimicamente perigosas ou explosivas.
    Retorna lista de alertas críticos (strings).
    """
    alertas = []
    nomes = list(dados_compostos.keys())
    tipos = [set(dados['grupos_funcionais']) for dados in dados_compostos.values()]
    
    # Regra 1: Metal alcalino + Água → explosão
    metais_alcalinos = any('Metal Alcalino' in grupos for grupos in tipos)
    if metais_alcalinos and 'water' in nomes:
        alertas.append(
            "💥 **PERIGO EXTREMO!** Metais alcalinos (como sódio ou potássio) reagem **explosivamente** com água, "
            "liberando gás hidrogênio inflamável e calor intenso. **NUNCA misture!**"
        )
    
    # Regra 2: Cloretos de ácido + Água → reação violenta
    cloretos_acido = any('Cloreto de Ácido' in grupos for grupos in tipos)
    if cloretos_acido and 'water' in nomes:
        alertas.append(
            "⚠️ **REAÇÃO VIOLENTA!** Cloretos de ácido (ex: cloreto de acetila) hidrolisam rapidamente em água, "
            "liberando ácido clorídrico corrosivo e calor. Use com extrema cautela em ambiente anidro."
        )
    
    # Regra 3: Cloreto de sulfurila + Água
    sulfurila = any('Cloreto de Sulfurila' in grupos for grupos in tipos)
    if sulfurila and 'water' in nomes:
        alertas.append(
            "☠️ **LIBERAÇÃO DE GASES TÓXICOS!** Cloreto de sulfurila reagem com água, liberando **SO₂ e HCl**, ambos tóxicos e corrosivos. "
            "Realize apenas em capela com proteção adequada."
        )
    
    # Regra 4: Peróxidos + Redutores (ex: álcoois, metais) → risco de incêndio/explosão
    peroxido = any('Peróxido' in grupos for grupos in tipos)
    redutores = any(any(g in ['Álcool', 'Metal Alcalino'] for g in grupos) for grupos in tipos)
    if peroxido and redutores:
        alertas.append(
            "🔥 **RISCO DE INCÊNDIO/EXPLOSÃO!** Peróxidos (como H₂O₂) são oxidantes fortes e podem reagir violentamente com redutores "
            "(álcoois, metais). Evite contato direto."
        )
    
    # Regra 5: Ácidos fortes + Bases fortes → calor intenso (ex: HCl + NaOH)
    acido_forte = any('Ácido Forte' in grupos for grupos in tipos)
    base_forte = any('Base Forte' in grupos for grupos in tipos)
    if acido_forte and base_forte:
        alertas.append(
            "🌡️ **REAÇÃO EXOTÉRMICA INTENSA!** Ácidos e bases fortes reagem com liberação significativa de calor. "
            "Adicione lentamente com agitação e resfriamento."
        )
    
    return alertas

# ==============================
# SUGESTOR DE COMPOSTOS (MANTIDO ORIGINAL)
# ==============================
class SugestorCompostos:
    def __init__(self):
        self.compostos_base = COMPOSTOS_BASE
        self._criar_indices()
    
    def _criar_indices(self):
        self.todos_sinonimos = []
        for nome, dados in self.compostos_base.items():
            sinonimos = dados.get('sinonimos', [])
            self.todos_sinonimos.extend(sinonimos)
            self.todos_sinonimos.append(nome)
        self.todos_sinonimos = list(set(self.todos_sinonimos))
    
    def buscar_sugestoes(self, entrada, max_sugestoes=5):
        entrada = entrada.lower().strip()
        sugestoes = []
        candidatos = get_close_matches(entrada, self.todos_sinonimos, n=max_sugestoes*2, cutoff=0.3)
        
        for candidato in candidatos:
            nome_principal = self._encontrar_nome_principal(candidato)
            if nome_principal and nome_principal not in [s['nome'] for s in sugestoes]:
                dados = self.compostos_base[nome_principal]
                sugestoes.append({
                    'nome': nome_principal,
                    'sinonimo_encontrado': candidato,
                    'cas': dados.get('cas', ''),
                    'formula': dados.get('formula', ''),
                    'tipo': dados.get('tipo', ''),
                    'score': self._calcular_score_relevancia(entrada, candidato)
                })
        
        sugestoes.sort(key=lambda x: x['score'], reverse=True)
        return sugestoes[:max_sugestoes]
    
    def _encontrar_nome_principal(self, sinonimo):
        for nome, dados in self.compostos_base.items():
            if sinonimo.lower() == nome.lower():
                return nome
            if sinonimo.lower() in [s.lower() for s in dados.get('sinonimos', [])]:
                return nome
        return None
    
    def _calcular_score_relevancia(self, entrada, candidato):
        entrada = entrada.lower()
        candidato = candidato.lower()
        score = 0
        if entrada == candidato: score += 100
        if candidato.startswith(entrada): score += 30
        if entrada in candidato: score += 20
        return score

# ==============================
# VALIDADOR DE COMPOSTOS (MANTIDO ORIGINAL)
# ==============================
class ValidadorCompostos:
    def __init__(self):
        self.compostos_validos = COMPOSTOS_BASE.copy()
        self.sugestor = SugestorCompostos()
        self.buscador = BuscadorPubChem()
        self._criar_mapa_cas()
        self._criar_mapa_sinonimos()

    def _criar_mapa_cas(self):
        self.mapa_cas = {}
        for nome, dados in self.compostos_validos.items():
            cas = dados.get('cas', '')
            if cas and cas.strip():
                self.mapa_cas[cas] = nome

    def _criar_mapa_sinonimos(self):
        self.mapa_sinonimos = {}
        for nome, dados in self.compostos_validos.items():
            self.mapa_sinonimos[nome.lower()] = nome
            for sinonimo in dados.get('sinonimos', []):
                self.mapa_sinonimos[sinonimo.lower()] = nome

    def validar_composto(self, entrada):
        try:
            entrada = entrada.strip()
            if not entrada:
                return False, "", None, 'vazio', []

            sugestoes = []
            entrada_lower = entrada.lower()

            if self._eh_numero_cas(entrada):
                return self._validar_por_cas(entrada, sugestoes)

            resultado_nome = self._validar_por_nome(entrada_lower)
            if resultado_nome:
                return resultado_nome

            resultado_pubchem = self._validar_por_pubchem(entrada)
            if resultado_pubchem:
                return resultado_pubchem

            sugestoes = self.sugestor.buscar_sugestoes(entrada)
            return False, entrada, None, 'nome', sugestoes

        except Exception as e:
            print(f"❌ Erro na validação de '{entrada}': {e}")
            return False, entrada, None, 'erro', []

    def _eh_numero_cas(self, entrada):
        return bool(re.match(r'^\d{2,7}-\d{1,2}-\d$', entrada))

    def _validar_por_cas(self, cas, sugestoes):
        if cas in self.mapa_cas:
            nome = self.mapa_cas[cas]
            return True, nome, self.compostos_validos[nome], 'cas', sugestoes
        else:
            resultado_pubchem = self.buscador.buscar_por_cas(cas)
            if resultado_pubchem:
                dados_basicos = self._criar_dados_basicos_pubchem(resultado_pubchem, cas)
                return True, cas, dados_basicos, 'cas_pubchem', sugestoes
            sugestoes = self.sugestor.buscar_sugestoes(cas)
            return False, cas, None, 'cas', sugestoes

    def _validar_por_nome(self, entrada_lower):
        if entrada_lower in self.mapa_sinonimos:
            nome_principal = self.mapa_sinonimos[entrada_lower]
            return True, nome_principal, self.compostos_validos[nome_principal], 'nome', []
        return None

    def _validar_por_pubchem(self, entrada):
        resultado_pubchem = self.buscador.buscar_por_nome(entrada)
        if resultado_pubchem:
            dados_basicos = self._criar_dados_basicos_pubchem(resultado_pubchem, entrada)
            return True, entrada, dados_basicos, 'nome_pubchem', []
        return None

    def _criar_dados_basicos_pubchem(self, resultado_pubchem, entrada_original):
        pubchem_cid = resultado_pubchem.get('pubchem_cid', '')
        pubchem_url = resultado_pubchem.get('pubchem_url', f'https://pubchem.ncbi.nlm.nih.gov/compound/{pubchem_cid}' if pubchem_cid else 'https://pubchem.ncbi.nlm.nih.gov')
        
        return {
            'formula': resultado_pubchem.get('formula', 'Desconhecida'),
            'peso_molecular': resultado_pubchem.get('peso_molecular', 100.0),
            'logp': resultado_pubchem.get('logp', 0.0),
            'grupos_funcionais': ['Composto do PubChem'],
            'tipo': 'desconhecido',
            'descricao': f'Composto identificado via PubChem: {entrada_original}',
            'pubchem_cid': pubchem_cid,
            'pubchem_url': pubchem_url,
            'cas': entrada_original if self._eh_numero_cas(entrada_original) else resultado_pubchem.get('cas', ''),
            'sinonimos': [entrada_original]
        }

    def validar_lista_compostos(self, lista_compostos):
        compostos_validos = []
        compostos_invalidos = []
        resultados_detalhados = []
        
        entradas_unicas = list(dict.fromkeys([entrada.strip() for entrada in lista_compostos if entrada.strip()]))
        
        for entrada in entradas_unicas:
            valido, nome, dados, tipo, sugestoes = self.validar_composto(entrada)
            
            resultado = {
                'entrada_original': entrada,
                'valido': valido,
                'nome_normalizado': nome if valido else entrada,
                'dados': dados,
                'tipo_entrada': tipo,
                'sugestoes': sugestoes
            }
            
            resultados_detalhados.append(resultado)
            
            if valido:
                if nome not in compostos_validos:
                    compostos_validos.append(nome)
            else:
                compostos_invalidos.append({
                    'entrada': entrada,
                    'sugestoes': sugestoes
                })
        
        compostos_validos.sort()
        return compostos_validos, compostos_invalidos, resultados_detalhados

# ==============================
# BUSCADOR PUBCHEM (MANTIDO ORIGINAL)
# ==============================
class BuscadorPubChem:
    def __init__(self):
        self.base_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    
    def _eh_numero_cas(self, texto):
        """Verifica se o texto é um número CAS válido"""
        return bool(re.match(r'^\d{2,7}-\d{2}-\d$', texto))
    
    def buscar_por_nome_ou_cas(self, identificador):
        """Busca composto no PubChem por nome ou CAS e retorna dados completos"""
        # Tenta como nome primeiro
        resultado = self._buscar_como_nome(identificador)
        if resultado:
            return resultado
        
        # Se falhar, tenta como CAS
        if self._eh_numero_cas(identificador):
            resultado = self._buscar_como_cas(identificador)
            if resultado:
                return resultado
        
        return None
    
    def _buscar_como_nome(self, nome):
        """Busca composto por nome no PubChem"""
        try:
            url = f"{self.base_url}/compound/name/{nome}/JSON"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                cid = data['PC_Compounds'][0]['id']['id']['cid']
                return self._extrair_propriedades_completas(cid, nome)
        except Exception as e:
            print(f"Erro ao buscar '{nome}' no PubChem: {e}")
        return None
    
    def _buscar_como_cas(self, cas):
        """Busca composto por número CAS no PubChem"""
        try:
            # CORREÇÃO: usar endpoint correto para CAS
            url = f"{self.base_url}/compound/cas/{cas}/JSON"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                cid = data['PC_Compounds'][0]['id']['id']['cid']
                return self._extrair_propriedades_completas(cid, cas)
        except Exception as e:
            print(f"Erro ao buscar CAS '{cas}' no PubChem: {e}")
        return None
    
    def _extrair_propriedades_completas(self, cid, identificador):
        """Extrai propriedades completas do composto do PubChem"""
        try:
            # Buscar propriedades: fórmula, peso molecular, logP
            props_url = f"{self.base_url}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,XLogP3/JSON"
            response = requests.get(props_url, timeout=10)
            
            if response.status_code == 200:
                props_data = response.json()
                props = props_data['PropertyTable']['Properties'][0]
                
                formula = props.get('MolecularFormula', 'Desconhecida')
                peso = float(props.get('MolecularWeight', 0.0))
                logp = props.get('XLogP3')
                
                # Determinar tipo baseado no logP
                if logp is None:
                    tipo = 'desconhecido'
                elif logp < 0:
                    tipo = 'polar'
                elif logp < 2:
                    tipo = 'moderado'
                else:
                    tipo = 'apolar'
                
                return {
                    'formula': formula,
                    'peso_molecular': peso,
                    'logp': logp,
                    'grupos_funcionais': ['Composto do PubChem'],
                    'tipo': tipo,
                    'descricao': f'Composto identificado via PubChem: {identificador}',
                    'pubchem_cid': str(cid),
                    'pubchem_url': f'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}',
                    'cas': identificador if self._eh_numero_cas(identificador) else '',
                    'sinonimos': [identificador]
                }
        except Exception as e:
            print(f"Erro ao extrair propriedades do CID {cid}: {e}")
        
        return None
    
    # MÉTODOS DE COMPATIBILIDADE (mantenha para não quebrar o código existente)
    def buscar_por_cas(self, numero_cas):
        """Método legado - usa a nova implementação"""
        return self.buscar_por_nome_ou_cas(numero_cas)
    
    def buscar_por_nome(self, nome):
        """Método legado - usa a nova implementação"""
        return self.buscar_por_nome_ou_cas(nome)
    
    def _obter_detalhes_composto(self, cid, identificador):
        """Método legado - mantido para compatibilidade"""
        resultado = self._extrair_propriedades_completas(cid, identificador)
        if resultado:
            return resultado
        return {
            'pubchem_cid': str(cid),
            'pubchem_url': f'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}',
            'identificador': identificador
        }

# ==============================
# LABORATÓRIO PRINCIPAL (ATUALIZADO COM PLANOS)
# ==============================
class LaboratorioMiscibilidade:
    def __init__(self):
        self.versao = "3.0 - Integrado"
        self.validador = ValidadorCompostos()
        self.gerenciador_planos = GerenciadorPlanos()

    def validar_compostos(self, compostos_texto):
        compostos = self._processar_entrada(compostos_texto)
        compostos_validos, compostos_invalidos, detalhes = self.validador.validar_lista_compostos(compostos)
        
        resultado = {
            'valid_compounds': [],
            'invalid_compounds': compostos_invalidos,
            'total_valid': len(compostos_validos),
            'total_invalid': len(compostos_invalidos)
        }
        
        for detalhe in detalhes:
            if detalhe['valido']:
                resultado['valid_compounds'].append({
                    'name': detalhe['nome_normalizado'],
                    'input_type': detalhe['tipo_entrada'],
                    'original_input': detalhe['entrada_original'],
                    'data': detalhe['dados']
                })
        
        return resultado

    def analisar_compostos(self, compostos_texto, usuario_plano='free'):
        try:
            compostos = self._processar_entrada(compostos_texto)
            
            # Verificar limite do plano
            if not self.gerenciador_planos.verificar_limite_compostos(usuario_plano, len(compostos)):
                return self._criar_html_erro(
                    f"❌ Limite do plano excedido. Seu plano {usuario_plano} permite até {self.gerenciador_planos.limites[usuario_plano]['compostos_por_analise']} compostos por análise."
                )
            
            if not compostos:
                return self._criar_html_erro("Nenhum composto válido encontrado")
            
            compostos_validos, compostos_invalidos, _ = self.validador.validar_lista_compostos(compostos)
            if not compostos_validos:
                return self._criar_html_erro("Nenhum composto válido para análise")
            
            dados_compostos = self._buscar_dados_compostos(compostos_validos)
            
            alertas_perigo = _avaliar_perigos_imediatos(dados_compostos)
            if alertas_perigo:
                return self._criar_html_perigo(alertas_perigo)
            
            analise = self._realizar_analise_completa(dados_compostos)
            return self._gerar_relatorio_completo(compostos_validos, dados_compostos, analise, compostos_invalidos)
        except Exception as e:
            return self._criar_html_erro(f"Erro durante a análise: {str(e)}")

    def analisar_com_ia(self, compostos_texto, usuario_plano='free'):
        try:
            # Verificar se plano permite IA
            if not self.gerenciador_planos.pode_usar_ia(usuario_plano):
                return self._criar_html_erro("❌ Recurso de IA não disponível para seu plano.")
            
            compostos = self._processar_entrada(compostos_texto)
            if not compostos:
                return self._criar_html_erro("Nenhum composto válido encontrado")
            
            compostos_validos, compostos_invalidos, _ = self.validador.validar_lista_compostos(compostos)
            if not compostos_validos:
                return self._criar_html_erro("Nenhum composto válido para análise")
            
            dados_compostos = self._buscar_dados_compostos(compostos_validos)
            
            alertas_perigo = _avaliar_perigos_imediatos(dados_compostos)
            if alertas_perigo:
                return self._criar_html_perigo(alertas_perigo)
            
            analise = self._realizar_analise_completa(dados_compostos)
            return self._gerar_analise_ana_ester_real(compostos_validos, dados_compostos, analise, compostos_invalidos)
        except Exception as e:
            return self._criar_html_erro(f"Erro na análise com IA: {str(e)}")

    def _processar_entrada(self, compostos_texto):
        return [c.strip() for c in compostos_texto.split(",") if c.strip()]

    def _buscar_dados_compostos(self, compostos):
        """Busca dados completos dos compostos"""
        dados_compostos = {}
        for nome in compostos:
            if nome in COMPOSTOS_BASE:
                dados_compostos[nome] = COMPOSTOS_BASE[nome]
            else:
                # Tenta buscar no PubChem
                dados_pubchem = self.validador.buscador.buscar_por_nome_ou_cas(nome)
                if dados_pubchem:
                    dados_compostos[nome] = dados_pubchem
                else:
                    # Fallback para compostos não encontrados
                    dados_compostos[nome] = {
                        'formula': 'Desconhecida', 
                        'peso_molecular': 100.0, 
                        'logp': 0.0,
                        'grupos_funcionais': ['Composto Identificado'], 
                        'tipo': 'desconhecido',
                        'descricao': f'Composto {nome}', 
                        'pubchem_cid': '',
                        'pubchem_url': 'https://pubchem.ncbi.nlm.nih.gov',
                        'cas': nome if re.match(r'^\d{2,7}-\d{2}-\d$', nome) else '',
                        'sinonimos': [nome]
                    }
        return dados_compostos

    def _criar_html_perigo(self, alertas):
        alertas_html = "".join(f"<p>{alerta}</p>" for alerta in alertas)
        return f"""
        <div class="alerta-critico">
            <h3>🚨 ANÁLISE BLOQUEADA POR SEGURANÇA</h3>
            {alertas_html}
            <p><strong>Este sistema prioriza sua segurança. Não tente reproduzir essas misturas em laboratório sem supervisão qualificada.</strong></p>
        </div>
        """

    def _realizar_analise_completa(self, dados_compostos):
        tipos = [dados['tipo'] for dados in dados_compostos.values()]
        logps = [dados['logp'] if dados['logp'] is not None else 0 for dados in dados_compostos.values()]
        amplitude = max(logps) - min(logps) if logps else 0
        media_logp = sum(logps) / len(logps) if logps else 0

        if all(tipo == 'polar' for tipo in tipos):
            miscibilidade, confianca, cor = "MISCÍVEL ✅", "Alta - Todos os compostos são polares", "#4CAF50"
        elif all(tipo == 'apolar' for tipo in tipos):
            miscibilidade, confianca, cor = "MISCÍVEL ✅", "Alta - Todos os compostos são apolares", "#4CAF50"
        elif 'surfactante' in tipos:
            miscibilidade, confianca, cor = "EMULSÃO ESTÁVEL 🧴", "Alta - Presença de surfactante", "#2196F3"
        elif amplitude > 4:
            miscibilidade, confianca, cor = "SEPARAÇÃO DE FASES ⚠️", "Alta - Diferentes polaridades", "#FF9800"
        elif amplitude > 2:
            miscibilidade, confianca, cor = "MISCÍVEL COM AGITAÇÃO 🔄", "Média - Pode formar emulsão", "#FFB300"
        else:
            miscibilidade, confianca, cor = "MISCÍVEL ✅", "Alta - Polaridades similares", "#4CAF50"

        interacoes_pares = []
        compostos_lista = list(dados_compostos.keys())
        for i in range(len(compostos_lista)):
            for j in range(i + 1, len(compostos_lista)):
                comp1, comp2 = compostos_lista[i], compostos_lista[j]
                dados1, dados2 = dados_compostos[comp1], dados_compostos[comp2]
                logp1 = dados1['logp'] if dados1['logp'] is not None else 0
                logp2 = dados2['logp'] if dados2['logp'] is not None else 0
                delta_logp = abs(logp1 - logp2)
                if dados1['tipo'] == dados2['tipo']:
                    miscivel, razao = True, "Mesmo tipo de polaridade"
                elif delta_logp < 2:
                    miscivel, razao = True, "Polaridades similares"
                else:
                    miscivel, razao = False, "Polaridades diferentes"
                interacoes_pares.append({
                    'composto1': comp1, 'composto2': comp2, 'miscivel': miscivel,
                    'razao': razao, 'delta_logp': delta_logp
                })

        return {
            'miscibilidade_geral': miscibilidade, 'confianca_geral': confianca, 'cor_geral': cor,
            'estatisticas': {'media_logp': media_logp, 'amplitude': amplitude, 'num_compostos': len(dados_compostos), 'tipos_compostos': len(set(tipos))},
            'interacoes_pares': interacoes_pares
        }

    def _gerar_relatorio_completo(self, compostos, dados_compostos, analise, compostos_invalidos=None):
        html = f"""
        <div style="background: linear-gradient(135deg, #1a237e 0%, #283593 100%); color: white; padding: 25px; border-radius: 10px; text-align: center; margin: 10px 0;">
            <h1>🧪 RELATÓRIO COMPLETO DE MISCIBILIDADE</h1>
            <h2>{', '.join(compostos)}</h2>
            <p>Versão {self.versao} | Sistema com Segurança Laboratorial</p>
        </div>
        """
        
        if compostos_invalidos:
            html += f"""
            <div style="background: #FFF3E0; padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 5px solid #FF9800;">
                <h4>⚠️ Atenção: {len(compostos_invalidos)} composto(s) não reconhecido(s)</h4>
                <p><strong>Não analisados:</strong> {', '.join([comp['entrada'] for comp in compostos_invalidos])}</p>
                <p><em>A análise foi realizada apenas com os compostos válidos.</em></p>
            </div>
            """
        
        html += f"""
        <div style="background: {analise['cor_geral']}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0;">
            <h2>📊 {analise['miscibilidade_geral']}</h2>
            <p>{analise['confianca_geral']}</p>
            <p>Polaridade média: {analise['estatisticas']['media_logp']:.2f} | Amplitude: {analise['estatisticas']['amplitude']:.2f}</p>
        </div>
        
        <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h3>🔬 COMPOSTOS ANALISADOS</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px;">
        """
        
        for nome, dados in dados_compostos.items():
            cor_tipo = {'polar': '#42A5F5', 'apolar': '#FFA000', 'surfactante': '#9C27B0', 'reativo': '#F44336', 'desconhecido': '#757575'}.get(dados['tipo'], '#757575')
            tem_pubchem = bool(dados.get('pubchem_cid'))
            link_pubchem = f'<a href="{dados["pubchem_url"]}" target="_blank" class="pubchem-link">🔗 Ver no PubChem 3D</a>' if tem_pubchem else '<span style="background: #757575; color: white; padding: 8px 16px; border-radius: 20px; font-size: 14px;">🔍 Dados limitados</span>'
            logp_text = f"{dados['logp']:.2f}" if dados['logp'] is not None else "N/A"

            html += f"""
            <div class="compound-card" style="border-left-color: {cor_tipo}">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
                    <h4 style="margin: 0;">🧪 {nome.title()}</h4>
                    <span style="background: {cor_tipo}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 12px; font-weight: bold;">{dados['tipo'].upper()}</span>
                </div>
                <div style="background: #f9f9f9; padding: 15px; border-radius: 8px;">
                    <p><strong>🧪 Fórmula:</strong> {dados['formula']}</p>
                    <p><strong>⚖️ Massa Molecular:</strong> {dados['peso_molecular']:.2f} g/mol</p>
                    <p><strong>📊 Coeficiente de Partição (logP):</strong> {logp_text}</p>
                    <p><strong>🔗 Grupos Funcionais:</strong></p>
                    <div style="display: flex; flex-wrap: wrap; gap: 5px; margin: 10px 0;">
            """
            for grupo in dados['grupos_funcionais']:
                cor_grupo = self._obter_cor_grupo_funcional(grupo)
                html += f'<span style="background: {cor_grupo}; color: white; padding: 4px 8px; border-radius: 15px; font-size: 11px; font-weight: bold;">{grupo}</span>'
            html += f"""
                    </div>
                    <p><strong>📝 Descrição:</strong> {dados['descricao']}</p>
                    <div style="margin-top: 15px;">{link_pubchem}</div>
                </div>
            </div>
            """
        html += "</div></div>"

        html += """
        <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h3>🔗 ANÁLISE DAS INTERAÇÕES ENTRE COMPOSTOS</h3>
        """
        for interacao in analise['interacoes_pares']:
            cor = "#4CAF50" if interacao['miscivel'] else "#F44336"
            emoji = "✅" if interacao['miscivel'] else "❌"
            html += f"""
            <div style="background: white; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 5px solid {cor};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{emoji} {interacao['composto1']} + {interacao['composto2']}</strong><br>
                        <span style="color: {cor}; font-weight: bold;">{interacao['razao']}</span>
                    </div>
                    <div style="text-align: right;">
                        <small>ΔlogP: {interacao['delta_logp']:.2f}</small>
                    </div>
                </div>
            </div>
            """
        html += "</div>"
        
        return html

    def _gerar_analise_ana_ester_real(self, compostos, dados_compostos, analise, compostos_invalidos=None):
        desc_compostos = []
        for nome, dados in dados_compostos.items():
            logp_text = f"{dados['logp']:.2f}" if dados['logp'] is not None else "N/A"
            desc = f"- {nome.title()}: {dados['descricao']}, logP={logp_text}, tipo={dados['tipo']}"
            desc_compostos.append(desc)

        prompt = f"""
Você é Ana Ester, uma química especialista em sustentabilidade, miscibilidade e inovação com propósito.
Analise o seguinte sistema de compostos químicos com profundidade técnica, consciência ambiental e clareza pedagógica.

Compostos: {', '.join(compostos)}
Dados técnicos:
{chr(10).join(desc_compostos)}

{"⚠️ ATENÇÃO: Alguns compostos não foram reconhecidos e não estão incluídos na análise." if compostos_invalidos else ""}

Análise preliminar do sistema:
- Miscibilidade geral: {analise['miscibilidade_geral']}
- Confiança: {analise['confianca_geral']}
- Polaridade média: {analise['estatisticas']['media_logp']:.2f}
- Amplitude de logP: {analise['estatisticas']['amplitude']:.2f}

Forneça uma resposta com:
1. Uma avaliação técnica clara da miscibilidade.
2. Recomendações práticas para laboratório ou indústria.
3. Considerações sobre sustentabilidade e segurança.
4. Uma breve reflexão filosófica ou inspiradora sobre a química.

Mantenha um tom profissional, empático e inspirador. Use emojis estratégicos para melhorar a legibilidade.
Limite a resposta a 300–400 palavras.
"""

        headers = {
            "Authorization": f"Bearer {OPENROVER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chemteqsolutions.pythonanywhere.com",
            "X-Title": "ChemTeq Solutions - Laboratório Virtual"
        }

        payload = {
            "model": MODEL_ANA_ESTER,
            "messages": [
                {"role": "system", "content": "Você é Ana Ester, química especialista em solventes, miscibilidade e química verde."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        try:
            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=25)
            response.raise_for_status()
            ai_response = response.json()['choices'][0]['message']['content']
        except Exception as e:
            ai_response = self._gerar_analise_ana_ester_fallback(compostos, dados_compostos, analise, compostos_invalidos)

        html = f"""
        <div class='ana-ester-section'>
            <div style='text-align: center; margin-bottom: 20px;'>
                <h3>🧠 Ana Ester - ChemTeq Solutions (via Llama 3.1)</h3>
                <p><em>Conectando química, sustentabilidade e propósito</em></p>
            </div>
            <div class='chat-message ai-message'>
                {ai_response.replace('\n', '<br>')}
            </div>
            <div style='text-align: center; color: #666; margin-top: 20px;'>
                <p><em>Ana Ester - ChemTeq Solutions<br>"Tecnologia com propósito, inovação com valores humanos"</em></p>
            </div>
        </div>
        """
        return html

    def _gerar_analise_ana_ester_fallback(self, compostos, dados_compostos, analise, compostos_invalidos=None):
        if analise['miscibilidade_geral'] == "MISCÍVEL ✅":
            perspectiva = "O sistema apresenta excelente compatibilidade molecular."
            recomendacao = "Pode ser utilizado diretamente sem necessidade de agentes emulsificantes."
        elif "EMULSÃO" in analise['miscibilidade_geral']:
            perspectiva = "Forma uma emulsão estável, ideal para aplicações bifásicas."
            recomendacao = "Mantenha agitação moderada para estabilidade do sistema."
        else:
            perspectiva = "Desafios de miscibilidade refletem diversidade molecular."
            recomendacao = "Considere co-solventes ou surfactantes para melhorar a compatibilidade."

        return (f"💡 **Perspectiva Técnica**: {perspectiva} Polaridade média: {analise['estatisticas']['media_logp']:.2f}.<br>"
                f"🌱 **Sustentabilidade**: Prefira solventes verdes e minimize resíduos. Avalie o ciclo de vida dos compostos.<br>"
                f"🔬 **Recomendação Prática**: {recomendacao}<br>"
                f"🔗 **Visualização**: Use os links PubChem para explorar estruturas 3D das moléculas.<br>"
                f"💭 **Reflexão Filosófica**: A química nos ensina que diversidade pode gerar harmonia ou separação — ambas com propósito específico na natureza.")

    def _obter_cor_grupo_funcional(self, grupo):
        cores = {
            'Água': '#2196F3', 'Álcool': '#4CAF50', 'Hidroxila': '#45a049', 'Polar': '#42A5F5',
            'Apolar': '#FFA000', 'Surfactante': '#9C27B0', 'Sulfato': '#7B1FA2', 'Cetona': '#E91E63',
            'Halogenado': '#795548', 'Alcano': '#607D8B', 'Aromático': '#FF5722', 'Lipídio': '#FF9800',
            'Poliálcool': '#009688', 'Aniônico': '#3F51B5', 'Ácido Carboxílico': '#F44336', 'Éter': '#FFB300',
            'Antibacteriano': '#8BC34A', 'Fenol': '#795548', 'Clorado': '#388E3C', 'Parabeno': '#7B1FA2',
            'Conservante': '#5D4037', 'Éster': '#FF9800', 'Silicona': '#455A64', 'Emoliente': '#FF5722',
            'Composto do PubChem': '#757575', 'Composto Identificado': '#9E9E9E',
            'Metal Alcalino': '#FF5722', 'Redutor Forte': '#D32F2F', 'Cloreto de Ácido': '#F57C00',
            'Eletrofílico': '#FF9800', 'Cloreto de Sulfurila': '#E65100', 'Reagente de Cloração': '#BF360C',
            'Peróxido': '#FF6D00', 'Oxidante Forte': '#DD2C00', 'Base Forte': '#2962FF', 'Hidróxido': '#2979FF',
            'Corrosivo': '#D50000', 'Ácido Forte': '#C62828'
        }
        return cores.get(grupo, '#757575')

    def _criar_html_erro(self, mensagem):
        return f"""
        <div style="background: #ffebee; color: #c62828; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h3>❌ Erro na Análise</h3>
            <p>{mensagem}</p>
            <p>Verifique os nomes dos compostos e tente novamente.</p>
        </div>
        """

# ==============================
# CONTINUAÇÃO DO TEMPLATE HTML
# ==============================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Laboratório Virtual de Miscibilidade - ChemTeq Solutions</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* ESTILOS COMPLETOS */
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin: 20px 0;
        }
        .header {
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
        }
        .input-section {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            border-left: 5px solid #4CAF50;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
            font-size: 16px;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus {
            border-color: #4CAF50;
            outline: none;
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }
        button {
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            margin-right: 12px;
            margin-bottom: 10px;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
        }
        button.ia-button {
            background: linear-gradient(135deg, #9C27B0 0%, #7B1FA2 100%);
            box-shadow: 0 4px 15px rgba(156, 39, 176, 0.3);
        }
        button.examples-button {
            background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
            box-shadow: 0 4px 15px rgba(33, 150, 243, 0.3);
        }
        button.validate-button {
            background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
            box-shadow: 0 4px 15px rgba(255, 152, 0, 0.3);
        }
        .result {
            margin-top: 30px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
            background: #e3f2fd;
            border-radius: 10px;
            margin: 20px 0;
        }
        .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4CAF50;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .example {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin: 12px 0;
            cursor: pointer;
            border-left: 4px solid #2196F3;
            transition: all 0.3s;
        }
        .example:hover {
            background: #bbdefb;
            transform: translateX(5px);
        }
        .examples-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .example-category {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .validation-result {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .valid-compound {
            background: #e8f5e8;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid #4CAF50;
        }
        .invalid-compound {
            background: #ffebee;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid #F44336;
        }
        .suggestions {
            background: #FFF3E0;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid #FF9800;
        }
        .suggestion-item {
            background: white;
            padding: 12px;
            margin: 8px 0;
            border-radius: 6px;
            border: 1px solid #FFE0B2;
            cursor: pointer;
            transition: all 0.2s;
        }
        .suggestion-item:hover {
            background: #FFF3E0;
            transform: translateX(5px);
        }
        .compound-badge {
            display: inline-flex;
            align-items: center;
            background: #2196F3;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .cas-badge {
            background: #9C27B0;
        }
        .pubchem-link {
            display: inline-flex;
            align-items: center;
            background: #2E7D32;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            text-decoration: none;
            font-size: 14px;
            font-weight: bold;
            margin-top: 10px;
            transition: all 0.3s;
        }
        .pubchem-link:hover {
            background: #1B5E20;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .compound-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #4CAF50;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .info-box {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #2196F3;
        }
        .suggestion-badge {
            background: #FF9800;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            margin-left: 8px;
        }
        .ana-ester-section {
            background: linear-gradient(135deg, #f3e5f5 0%, #e8f5e8 100%);
            padding: 25px;
            border-radius: 10px;
            margin: 25px 0;
            border-left: 5px solid #9C27B0;
        }
        .chat-message {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            line-height: 1.6;
        }
        .ai-message {
            border-left: 4px solid #9C27B0;
        }
        .user-info {
            background: #e8f5e8;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #4CAF50;
        }
        .plan-badge {
            display: inline-block;
            background: #FF9800;
            color: white;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .premium { background: #9C27B0; }
        .enterprise { background: #F44336; }
        .alerta-critico {
            background: #ffebee;
            color: #c62828;
            padding: 25px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 5px solid #c62828;
            font-weight: bold;
        }
        .security-warning {
            background: #fff3e0;
            color: #ef6c00;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #ef6c00;
        }
        .interaction-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .interaction-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .interaction-card.incompatible {
            border-left-color: #F44336;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-top: 4px solid #2196F3;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
            margin: 10px 0;
        }
        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }
            button {
                width: 100%;
                margin: 5px 0;
            }
            .examples-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Laboratório Virtual de Miscibilidade</h1>
            <h2>ChemTeq Solutions - Tecnologia com Propósito</h2>
            <p>Versão 3.0 - Integrado e Sistema com Detecção de Perigos</p>
        </div>

        <!-- Seção de Informações do Usuário -->
        <div id="userInfo" class="user-info" style="display: none;">
            <h3>👤 Informações do Usuário</h3>
            <p>Plano: <span id="userPlan" class="plan-badge">Free</span></p>
            <p id="userLimits">Limites: 5 compostos por análise, 10 análises/dia</p>
        </div>

        <!-- Seção de Entrada Principal -->
        <div class="input-section">
            <h3>🔬 Análise de Miscibilidade de Compostos</h3>
            <p>Digite os nomes dos compostos separados por vírgula (em inglês ou português):</p>
            
            <div class="input-group">
                <label for="compounds">Compostos:</label>
                <input type="text" id="compounds" placeholder="Ex: water, ethanol, hexane, sodium chloride" style="width: 100%;">
            </div>

            <div class="input-group">
                <label for="user_id">ID do Usuário (opcional):</label>
                <input type="text" id="user_id" placeholder="Seu ID de usuário">
            </div>

            <div class="input-group">
                <label for="user_email">Email do Usuário (opcional):</label>
                <input type="text" id="user_email" placeholder="Seu email">
            </div>

            <div>
                <button onclick="validateCompounds()" class="validate-button">✅ Validar Compostos</button>
                <button onclick="analyzeCompounds()" class="analyze-button">🔍 Analisar Miscibilidade</button>
                <button onclick="analyzeWithAI()" class="ia-button">🧠 Analisar com IA (Ana Ester)</button>
                <button onclick="showExamples()" class="examples-button">📚 Ver Exemplos</button>
            </div>
        </div>

        <!-- Loading Spinner -->
        <div id="loading" class="loading">
            <div class="loading-spinner"></div>
            <p>Analisando compostos e verificando segurança...</p>
            <p><small>Isso pode levar alguns segundos</small></p>
        </div>

        <!-- Seção de Resultados -->
        <div id="result" class="result"></div>

        <!-- Seção de Exemplos (inicialmente oculta) -->
        <div id="examplesSection" style="display: none;">
            <h3>📚 Exemplos Práticos</h3>
            <div class="examples-grid">
                <div class="example-category">
                    <h4>🧴 Cosméticos</h4>
                    <div class="example" onclick="loadExample('water, glycerol, cetearyl alcohol, dimethicone')">
                        <strong>Emulsão O/A</strong><br>
                        água, glicerol, álcool cetílico, dimeticone
                    </div>
                    <div class="example" onclick="loadExample('water, ethanol, glycerin, benzophenone-3')">
                        <strong>Protetor Solar</strong><br>
                        água, etanol, glicerina, benzofenona-3
                    </div>
                </div>
                <div class="example-category">
                    <h4>🔬 Solventes</h4>
                    <div class="example" onclick="loadExample('water, ethanol, acetone')">
                        <strong>Miscível</strong><br>
                        água, etanol, acetona
                    </div>
                    <div class="example" onclick="loadExample('water, hexane, oil')">
                        <strong>Separação de Fases</strong><br>
                        água, hexano, óleo
                    </div>
                </div>
                <div class="example-category">
                    <h4>⚠️ Perigosos</h4>
                    <div class="example" onclick="loadExample('sodium metal, water')">
                        <strong>Reação Explosiva</strong><br>
                        sódio metálico + água
                    </div>
                    <div class="example" onclick="loadExample('acetyl chloride, water')">
                        <strong>Reação Violenta</strong><br>
                        cloreto de acetila + água
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Função para carregar exemplo
        function loadExample(compounds) {
            document.getElementById('compounds').value = compounds;
            document.getElementById('examplesSection').style.display = 'none';
        }

        // Função para mostrar exemplos
        function showExamples() {
            const examplesSection = document.getElementById('examplesSection');
            examplesSection.style.display = examplesSection.style.display === 'none' ? 'block' : 'none';
        }

        // Função para validar compostos
        async function validateCompounds() {
            const compounds = document.getElementById('compounds').value;
            const userId = document.getElementById('user_id').value;
            const userEmail = document.getElementById('user_email').value;
            
            if (!compounds.trim()) {
                alert('Por favor, digite pelo menos um composto');
                return;
            }

            showLoading();
            
            try {
                const response = await fetch('/validate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        compounds: compounds,
                        user_id: userId || 'guest',
                        user_email: userEmail || 'guest@example.com'
                    })
                });
                
                const data = await response.json();
                displayValidationResult(data);
            } catch (error) {
                displayError('Erro na validação: ' + error.message);
            } finally {
                hideLoading();
            }
        }

        // Função para analisar miscibilidade
        async function analyzeCompounds() {
            const compounds = document.getElementById('compounds').value;
            const userId = document.getElementById('user_id').value;
            const userEmail = document.getElementById('user_email').value;
            
            if (!compounds.trim()) {
                alert('Por favor, digite pelo menos um composto');
                return;
            }

            showLoading();
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        compounds: compounds,
                        user_id: userId || 'guest',
                        user_email: userEmail || 'guest@example.com'
                    })
                });
                
                const html = await response.text();
                document.getElementById('result').innerHTML = html;
            } catch (error) {
                displayError('Erro na análise: ' + error.message);
            } finally {
                hideLoading();
            }
        }

        // Função para análise com IA
        async function analyzeWithAI() {
            const compounds = document.getElementById('compounds').value;
            const userId = document.getElementById('user_id').value;
            const userEmail = document.getElementById('user_email').value;
            
            if (!compounds.trim()) {
                alert('Por favor, digite pelo menos um composto');
                return;
            }

            showLoading();
            
            try {
                const response = await fetch('/analyze-ai', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        compounds: compounds,
                        user_id: userId || 'guest',
                        user_email: userEmail || 'guest@example.com'
                    })
                });
                
                const html = await response.text();
                document.getElementById('result').innerHTML = html;
            } catch (error) {
                displayError('Erro na análise com IA: ' + error.message);
            } finally {
                hideLoading();
            }
        }

        // Funções auxiliares
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').innerHTML = '';
        }

        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
        }

        function displayError(message) {
            document.getElementById('result').innerHTML = `
                <div style="background: #ffebee; color: #c62828; padding: 20px; border-radius: 10px;">
                    <h3>❌ Erro</h3>
                    <p>${message}</p>
                </div>
            `;
        }

        function displayValidationResult(data) {
            let html = '<div class="validation-result">';
            html += '<h3>✅ Resultado da Validação</h3>';
            
            if (data.valid_compounds && data.valid_compounds.length > 0) {
                html += '<h4>✔️ Compostos Válidos:</h4>';
                data.valid_compounds.forEach(compound => {
                    html += `<div class="valid-compound">
                        <strong>${compound.name}</strong>
                        <span class="compound-badge">${compound.input_type}</span>
                        <br><small>Entrada original: ${compound.original_input}</small>
                    </div>`;
                });
            }
            
            if (data.invalid_compounds && data.invalid_compounds.length > 0) {
                html += '<h4>❌ Compostos Inválidos:</h4>';
                data.invalid_compounds.forEach(compound => {
                    html += `<div class="invalid-compound">
                        <strong>${compound.entrada}</strong>
                        <p><em>Não reconhecido no sistema</em></p>`;
                    
                    if (compound.sugestoes && compound.sugestoes.length > 0) {
                        html += '<div class="suggestions"><strong>Sugestões:</strong>';
                        compound.sugestoes.forEach(sugestao => {
                            html += `<div class="suggestion-item" onclick="document.getElementById('compounds').value += ', ${sugestao.nome}'">
                                ${sugestao.nome} (${sugestao.formula}) - ${sugestao.tipo}
                                <span class="suggestion-badge">Score: ${sugestao.score}</span>
                            </div>`;
                        });
                        html += '</div>';
                    }
                    html += '</div>';
                });
            }
            
            html += `<div class="info-box">
                <strong>Resumo:</strong> ${data.total_valid} válidos, ${data.total_invalid} inválidos
            </div>`;
            
            html += '</div>';
            document.getElementById('result').innerHTML = html;
        }

        // Verificar usuário ao carregar a página (se fornecido)
        document.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const userId = urlParams.get('user_id');
            const userEmail = urlParams.get('user_email');
            
            if (userId && userEmail) {
                document.getElementById('user_id').value = userId;
                document.getElementById('user_email').value = userEmail;
                verifyUser(userId, userEmail);
            }
        });

        async function verifyUser(userId, userEmail) {
    try {
        const response = await fetch('/verify-user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                user_email: userEmail
            })
        });
        
        const data = await response.json();
        if (data.valid) {
            document.getElementById('userInfo').style.display = 'block';
            document.getElementById('userPlan').textContent = data.plan;
            document.getElementById('userPlan').className = `plan-badge ${data.plan}`;
            document.getElementById('userLimits').textContent = `Limites: ${data.limits.compostos_por_analise} compostos por análise, ${data.limits.analises_dia} análises/dia`;
            
            // ✅ CORREÇÃO: Usar ID correto
            document.getElementById('loginHeaderButton').style.display = 'none';
            document.getElementById('logoutButton').style.display = 'inline-block';
        }
    } catch (error) {
        console.log('Erro na verificação do usuário:', error);
    }
}
    </script>
</body>
        <!-- Modal de Login -->
        <div id="loginModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;">
            <div style="position: relative; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 10px; max-width: 400px; width: 90%;">
                <h3>🔐 Fazer Login</h3>
                <div style="margin: 20px 0;">
                    <input type="email" id="loginEmail" placeholder="Seu email" style="width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                    <input type="password" id="loginPassword" placeholder="Sua senha" style="width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                </div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="fazerLogin()" style="flex: 1;">Entrar</button>
                    <button onclick="fecharModal('loginModal')" style="background: #666;">Cancelar</button>
                </div>
                <p style="text-align: center; margin-top: 15px;">
                    <a href="javascript:void(0)" onclick="mostrarCadastro()" style="color: #2196F3;">Não tem conta? Cadastre-se</a>
                </p>
            </div>
        </div>

        <!-- Modal de Cadastro -->
        <div id="cadastroModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;">
            <div style="position: relative; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 10px; max-width: 400px; width: 90%;">
                <h3>📝 Criar Conta</h3>
                <div style="margin: 20px 0;">
                    <input type="text" id="cadastroNome" placeholder="Seu nome completo" style="width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                    <input type="email" id="cadastroEmail" placeholder="Seu email" style="width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                    <input type="password" id="cadastroPassword" placeholder="Sua senha (mín. 6 caracteres)" style="width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                </div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="fazerCadastro()" style="flex: 1;">Cadastrar</button>
                    <button onclick="fecharModal('cadastroModal')" style="background: #666;">Cancelar</button>
                </div>
                <p style="text-align: center; margin-top: 15px;">
                    <a href="javascript:void(0)" onclick="mostrarLogin()" style="color: #2196F3;">Já tem conta? Faça login</a>
                </p>
            </div>
        </div>
    </div>

    <script>
        // ==============================
        // FUNÇÕES DE AUTENTICAÇÃO (NOVO)
        // ==============================
        
        function mostrarLogin() {
            document.getElementById('loginModal').style.display = 'block';
            document.getElementById('cadastroModal').style.display = 'none';
        }

        function mostrarCadastro() {
            document.getElementById('cadastroModal').style.display = 'block';
            document.getElementById('loginModal').style.display = 'none';
        }

        function fecharModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        async function fazerLogin() {
    const email = document.getElementById('loginEmail').value;
    const senha = document.getElementById('loginPassword').value;
    
    if (!email || !senha) {
        alert('Por favor, preencha email e senha');
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: email, password: senha})
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Atualiza a interface com dados do usuário
            document.getElementById('userInfo').style.display = 'block';
            document.getElementById('userPlan').textContent = data.plan;
            document.getElementById('userPlan').className = `plan-badge ${data.plan}`;
            document.getElementById('userLimits').textContent = `Limites: ${data.limits.compostos_por_analise} compostos por análise, ${data.limits.analises_dia} análises/dia`;
            
            // Preenche os campos de usuário
            document.getElementById('user_id').value = data.user_id;
            document.getElementById('user_email').value = email;
            
            // Atualiza botões de login/logout
            document.querySelector('button[onclick="mostrarLogin()"]').style.display = 'none';
            document.getElementById('logoutButton').style.display = 'inline-block';
            
            fecharModal('loginModal');
            alert('✅ Login realizado com sucesso!');
            
            // OPÇÃO: Perguntar se quer ir para o laboratório ou ficar aqui
            if (confirm('Login realizado! Deseja ir para o Laboratório Principal?')) {
                window.location.href = 'https://chemteqsolutions.com/laboratorio';
            }
            
        } else {
            alert('❌ ' + data.message);
        }
    } catch (error) {
        alert('Erro no login: ' + error.message);
    }
}

        // ✅ CORREÇÃO: Usar a rota /register do Flask
async function fazerCadastro() {
    const nome = document.getElementById('cadastroNome').value;
    const email = document.getElementById('cadastroEmail').value;
    const senha = document.getElementById('cadastroPassword').value;
    
    if (!nome || !email || !senha) {
        alert('Por favor, preencha todos os campos');
        return;
    }
    
    if (senha.length < 6) {
        alert('A senha deve ter pelo menos 6 caracteres');
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: nome, 
                email: email, 
                password: senha
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Cadastro realizado com sucesso! Redirecionando...');
            // Redireciona para o laboratório após cadastro
            window.location.href = data.redirect_url || 'https://chemteqsolutions.com/laboratorio';
        } else {
            alert('❌ ' + data.message);
        }
    } catch (error) {
        alert('Erro no cadastro: ' + error.message);
    }
}

        function fazerLogout() {
            document.getElementById('userInfo').style.display = 'none';
            document.getElementById('user_id').value = '';
            document.getElementById('user_email').value = '';
            alert('👋 Logout realizado com sucesso!');
        }

        // Adiciona botão de login no header
        document.addEventListener('DOMContentLoaded', function() {
            const header = document.querySelector('.header');
            const loginButton = document.createElement('button');
            loginButton.innerHTML = '🔐 Login/Cadastro';
            loginButton.style.background = 'linear-gradient(135deg, #FF9800 0%, #F57C00 100%)';
            loginButton.style.marginTop = '15px';
            loginButton.onclick = mostrarLogin;
            
            header.appendChild(loginButton);
        });

    
        // Adiciona botão de login no header
document.addEventListener('DOMContentLoaded', function() {
    const header = document.querySelector('.header');
    
    // Botão de Login/Cadastro
    const loginButton = document.createElement('button');
    loginButton.innerHTML = '🔐 Login/Cadastro';
    loginButton.style.background = 'linear-gradient(135deg, #FF9800 0%, #F57C00 100%)';
    loginButton.style.marginTop = '15px';
    loginButton.style.marginRight = '10px';
    loginButton.onclick = mostrarLogin;
    loginButton.id = 'loginHeaderButton'; // ✅ ADD ID
    
    // Botão de Logout (inicialmente escondido)
    const logoutButton = document.createElement('button');
    logoutButton.innerHTML = '🚪 Sair';
    logoutButton.style.background = 'linear-gradient(135deg, #F44336 0%, #D32F2F 100%)';
    logoutButton.style.marginTop = '15px';
    logoutButton.style.display = 'none';
    logoutButton.onclick = fazerLogout;
    logoutButton.id = 'logoutButton';
    
    header.appendChild(loginButton);
    header.appendChild(logoutButton);
});


// Adiciona botão de logout no header
document.addEventListener('DOMContentLoaded', function() {
    const header = document.querySelector('.header');
    
    // Botão de Login/Cadastro
    const loginButton = document.createElement('button');
    loginButton.innerHTML = '🔐 Login/Cadastro';
    loginButton.style.background = 'linear-gradient(135deg, #FF9800 0%, #F57C00 100%)';
    loginButton.style.marginTop = '15px';
    loginButton.style.marginRight = '10px';
    loginButton.onclick = mostrarLogin;
    
    // Botão de Logout (inicialmente escondido)
    const logoutButton = document.createElement('button');
    logoutButton.innerHTML = '🚪 Sair';
    logoutButton.style.background = 'linear-gradient(135deg, #F44336 0%, #D32F2F 100%)';
    logoutButton.style.marginTop = '15px';
    logoutButton.style.display = 'none';
    logoutButton.onclick = fazerLogout;
    logoutButton.id = 'logoutButton';
    
    header.appendChild(loginButton);
    header.appendChild(logoutButton);
});
    </script>
</body>
</html>
'''

# ==============================
# ROTAS FLASK PRINCIPAIS
# ==============================

laboratorio = LaboratorioMiscibilidade()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/validate', methods=['POST'])
def validate_compounds():
    try:
        data = request.get_json()
        compounds_text = data.get('compounds', '')
        user_id = data.get('user_id', 'guest')
        user_email = data.get('user_email', 'guest@example.com')
        
        # Verificar usuário no WordPress
        user_valid, user_data = verificar_usuario_wordpress(user_id, user_email)
        user_plan = obter_plano_usuario(user_id) if user_valid else 'free'
        
        resultado = laboratorio.validar_compostos(compounds_text)
        
        return jsonify({
            'valid_compounds': resultado['valid_compounds'],
            'invalid_compounds': resultado['invalid_compounds'],
            'total_valid': resultado['total_valid'],
            'total_invalid': resultado['total_invalid'],
            'user_plan': user_plan,
            'user_valid': user_valid
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_compounds():
    try:
        data = request.get_json()
        compounds_text = data.get('compounds', '')
        user_id = data.get('user_id', 'guest')
        user_email = data.get('user_email', 'guest@example.com')
        
        # Verificar usuário e plano
        user_plan = 'guest'  # padrão para visitantes
        if user_id != 'guest' and user_email != 'guest@example.com':
            user_valid, user_data = verificar_usuario_wordpress(user_id, user_email)
            user_plan = obter_plano_usuario(user_id) if user_valid else 'guest'
        
        resultado_html = laboratorio.analisar_compostos(compounds_text, user_plan)
        return resultado_html
    except Exception as e:
        return f"<div class='alerta-critico'>Erro na análise: {str(e)}</div>"
    
@app.route('/analyze-ai', methods=['POST'])
def analyze_compounds_ai():
    try:
        data = request.get_json()
        compounds_text = data.get('compounds', '')
        user_id = data.get('user_id', 'guest')
        user_email = data.get('user_email', 'guest@example.com')
        
        # Verificar usuário e plano
        user_valid, user_data = verificar_usuario_wordpress(user_id, user_email)
        user_plan = obter_plano_usuario(user_id) if user_valid else 'free'
        
        resultado_html = laboratorio.analisar_com_ia(compounds_text, user_plan)
        return resultado_html
    except Exception as e:
        return f"<div class='alerta-critico'>Erro na análise com IA: {str(e)}</div>"

@app.route('/verify-user', methods=['POST'])
def verify_user():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_email = data.get('user_email')
        
        user_valid, user_data = verificar_usuario_wordpress(user_id, user_email)
        user_plan = obter_plano_usuario(user_id) if user_valid else 'free'
        
        return jsonify({
            'valid': user_valid,
            'plan': user_plan,
            'limits': laboratorio.gerenciador_planos.limites.get(user_plan, laboratorio.gerenciador_planos.limites['free']),
            'user_data': user_data
        })
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})
    
@app.route('/register', methods=['POST'])
def register_user():
    """Cadastra um novo usuário"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        if not email or not password or not name:
            return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Senha deve ter pelo menos 6 caracteres'})
        
        # Integração com WordPress
        success, user_id, message = criar_usuario_wordpress(email, password, name)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Cadastro realizado com sucesso!',
                'user_id': user_id,
                'redirect_url': 'https://chemteqsolutions.com/laboratorio'
            })
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro no cadastro: {str(e)}'})
    
# ==============================
# INICIALIZAÇÃO DA APLICAÇÃO
# ==============================

if __name__ == '__main__':
    print("=" * 60)
    print("🧪 LABORATÓRIO VIRTUAL DE MISCIBILIDADE")
    print("🏢 ChemTeq Solutions - Versão 3.0")
    print("🔗 Integrado com Base de Usuários")
    print("⚡ Sistema com Detecção de Perigos")
    print("🤖 IA: Ana Ester")
    print("=" * 60)
    print(f"📊 Base de dados: {len(COMPOSTOS_BASE)} compostos")
    print(f"🔐 Planos: Free, Premium, Enterprise")
    print(f"🌐 Servidor rodando em: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)