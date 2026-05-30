from flask import Flask, jsonify, request
from flask_cors import CORS
from iqoptionapi.stable_api import IQ_Option
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# 🔓 LIBERAR CORS PARA O LOVABLE E LOCALHOST
CORS(app, resources={r"/*": {"origins": ["*"]}})

iq = None
connected_email = None

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online", "connected": iq is not None and iq.check_connect()})

@app.route('/connect', methods=['POST'])
def connect():
    global iq, connected_email
    data = request.json
    email = data.get('email')
    password = data.get('password')
    account_type = data.get('account_type', 'PRACTICE')

    try:
        iq = IQ_Option(email, password)
        check, reason = iq.connect()

        if check:
            iq.change_balance(account_type)
            balance = iq.get_balance()
            connected_email = email
            logging.info(f"✅ Conectado: {email} | Saldo: {balance}")
            return jsonify({"success": True, "balance": balance, "account_type": account_type})
        else:
            logging.error(f"❌ Falha conexão: {reason}")
            return jsonify({"success": False, "reason": str(reason)}), 400
    except Exception as e:
        return jsonify({"success": False, "reason": str(e)}), 500

@app.route('/balance', methods=['GET'])
def get_balance():
    if not iq: return jsonify({"error": "Not connected"}), 400
    return jsonify({"balance": iq.get_balance()})

@app.route('/trade', methods=['POST'])
def trade():
    if not iq: return jsonify({"error": "Not connected"}), 400
    
    data = request.json
    amount = float(data.get('amount', 1))
    asset = data.get('asset', 'EURUSD')
    direction = data.get('direction', 'call').lower()
    duration = int(data.get('duration', 1))

    # Limpeza do nome do ativo
    asset_clean = asset.replace('/', '').replace('-OTC', '').upper()
    
    # Tentativa padrão
    status, trade_id = iq.buy(amount, asset_clean, direction, duration)

    if status:
        return jsonify({"success": True, "trade_id": trade_id, "otc": False})
    else:
        # Tentativa OTC (se disponível)
        try:
            status_otc, trade_id_otc = iq.buy(amount, asset_clean + '-OTC', direction, duration)
            if status_otc:
                return jsonify({"success": True, "trade_id": trade_id_otc, "otc": True})
        except: pass
        
        return jsonify({"success": False, "error": "Ativo indisponível ou rejeitado"}), 400

@app.route('/result/<int:trade_id>', methods=['GET'])
def get_result(trade_id):
    if not iq: return jsonify({"error": "Not connected"}), 400
    # iq.check_win_v3 retorna o lucro (float) ou None se ainda não fechou
    profit = iq.check_win_v3(trade_id)
    if profit is None:
        return jsonify({"trade_id": trade_id, "status": "pending", "profit": 0})
    return jsonify({"trade_id": trade_id, "status": "closed", "profit": profit})

@app.route('/assets', methods=['GET'])
def get_assets():
    if not iq: return jsonify({"error": "Not connected"}), 400
    try:
        open_times = iq.get_all_open_time()
        available = []
        # Filtra ativos Turbo (Binárias) abertos
        for name, data in open_times.get('turbo', {}).items():
            if data.get('open'):
                available.append(name)
        return jsonify({"assets": available})
    except:
        return jsonify({"assets": []})

if __name__ == '__main__':
    app.run(debug=False)