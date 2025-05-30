from flask import Flask, session, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import string
import re

app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE SETUP ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diagnosis.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class SolvedCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket = db.Column(db.String(12), unique=True, nullable=False)
    history = db.Column(db.Text, nullable=False)  # Store history as comma separated keys

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket = db.Column(db.String(12), nullable=False)
    comment = db.Column(db.Text, nullable=False)


# --- EXPERT SYSTEM NODES (unchanged) ---
NODES = {
    "start": {
        "question": "Apa gejala utama yang terlihat pada tanaman?",
        "options": {
            "Bercak pada daun": "node1",
            "Tanaman kerdil dan menguning": "node5",
            "Batang busuk atau lemah": "node8",
            "Bulir padi berubah warna atau berjamur": "node10"
        }
    },
    # Bercak pada daun
    "node1": {
        "question": "Seperti apa bentuk bercaknya?",
        "options": {
            "Sempit memanjang": "solusi1",
            "Melingkar/membulat": "node2",
            "Berbentuk garis memanjang dari ujung daun": "solusi6",
            "Berwarna oranye": "solusi11"
        }
    },
    "node2": {
        "question": "Bagaimana warna bercaknya?",
        "options": {
            "Cokelat kehitaman": "solusi2",
            "Kehijauan dan membentuk massa seperti jamur": "solusi3"
        }
    },
    # Tanaman kerdil dan menguning
    "node5": {
        "question": "Apakah daun menguning dan terdapat bercak hijau di sekeliling urat daun?",
        "options": {
            "Ya": "solusi4",
            "Tidak, daunnya tegak dan sempit": "solusi5",
            "Tidak, daun biasa tapi batang memanjang tidak normal": "solusi9"
        }
    },
    # Batang busuk
    "node8": {
        "question": "Di bagian mana batang terlihat membusuk?",
        "options": {
            "Pangkal batang dekat permukaan tanah": "solusi7",
            "Sepanjang batang atau pelepah": "solusi6",
            "Tidak jelas tapi menyebabkan rebah": "solusi7"
        }
    },
    # Bulir padi
    "node10": {
        "question": "Apakah ada benjolan hijau kehitaman menyerupai bola pada bulir?",
        "options": {
            "Ya": "solusi3",
            "Tidak, tetapi bulir mengering atau tidak berisi": "solusi12"
        }
    },
    # Solusi (penyakit)
    "solusi1": "Bercak Cokelat Sempit (Narrow Brown Spot)",
    "solusi2": "Bercak Cokelat (Brown Spot)",
    "solusi3": "Noda Palsu / Gosong (False Smut)",
    "solusi4": "Penyakit Tungro (Rice Tungro Disease)",
    "solusi5": "Rice Grassy Stunt",
    "solusi6": "Rice Sheath Blight",
    "solusi7": "Stem Rot",
    "solusi9": "Bakanae Disease",
    "solusi11": "Hawar Daun Jingga",
    "solusi12": "Penyakit Fusarium"
}

GLOSSARY = {
    "power supply": "Perangkat yang memasok daya listrik ke komputer.",
    "monitor": "Perangkat output visual untuk komputer.",
    "sistem operasi": "Perangkat lunak yang mengatur hardware dan software komputer."
}

# --- HELPERS ---

def generate_ticket():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def highlight_glossary(text):
    def repl(m):
        word = m.group(0).lower()
        if word in GLOSSARY:
            return f'<a href="{url_for("glossary", term=word)}" class="glossary-link">{word}</a>'
        return word
    pattern = re.compile('|'.join(re.escape(k) for k in GLOSSARY.keys()), re.IGNORECASE)
    return pattern.sub(repl, text)

def save_solved_case(history):
    ticket = generate_ticket()
    # Convert list to string with comma delimiter
    history_str = ','.join(history)
    new_case = SolvedCase(ticket=ticket, history=history_str)
    db.session.add(new_case)
    db.session.commit()
    return ticket

def get_history_by_ticket(ticket):
    case = SolvedCase.query.filter_by(ticket=ticket).first()
    if case:
        return case.history.split(',')
    return None

def save_feedback(ticket, comment):
    new_feedback = Feedback(ticket=ticket, comment=comment)
    db.session.add(new_feedback)
    db.session.commit()


# --- ROUTES ---

@app.route('/start-diagnosis')
def start_diagnosis():
    session.clear()
    session['history'] = ['start']
    return redirect(url_for('diagnosis'))

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        ticket_input = request.form.get('ticket_input', '').strip()
        if ticket_input:
            history = get_history_by_ticket(ticket_input)
            if history:
                qa_history = []
                for idx, node_key in enumerate(history):
                    node = NODES.get(node_key)
                    if isinstance(node, dict):
                        question = node.get('question', '')
                        answer = None
                        if idx + 1 < len(history):
                            next_key = history[idx + 1]
                            for a, n in node['options'].items():
                                if n == next_key:
                                    answer = a
                                    break
                        qa_history.append({'question': question, 'answer': answer})
                    elif isinstance(node, str):
                        qa_history.append({'question': 'Hasil Diagnosa', 'answer': node})
                return render_template('ticket.html', ticket=ticket_input, qa_history=qa_history)
            else:
                error = "Kode ticket tidak ditemukan."
    return render_template('index.html', error=error)

@app.route('/diagnosis', methods=['GET', 'POST'])
def diagnosis():
    history = session.get('history', ['start'])
    current = history[-1]
    node = NODES[current]

    if isinstance(node, str):
        highlighted = highlight_glossary(node)
        return render_template('result.html', result=highlighted)

    if request.method == 'POST':
        answer = request.form.get('answer')
        next_node = node['options'].get(answer)
        if next_node:
            history.append(next_node)
            session['history'] = history
            return redirect(url_for('diagnosis'))

    return render_template('question.html', question=node['question'], options=node['options'].keys())

@app.route('/confirm', methods=['POST'])
def confirm():
    answer = request.form.get('confirm')
    if answer == 'ya':
        history = session.get('history', [])
        ticket = save_solved_case(history)
        session.clear()
        return render_template('ticket_done.html', ticket=ticket)
    else:
        return redirect(url_for('error_check'))

@app.route('/error-check', methods=['GET', 'POST'])
def error_check():
    if request.method == 'POST':
        answer = request.form.get('error')
        if answer == 'ya':
            session['history'] = ['start']
            return redirect(url_for('diagnosis'))
        else:
            return redirect(url_for('detail_diagnosis'))
    return render_template('error_check.html')

@app.route('/detail-diagnosis', methods=['GET', 'POST'])
def detail_diagnosis():
    if request.method == 'POST':
        answer = request.form.get('detail')
        session['detail_answer'] = answer
        return redirect(url_for('final_confirmation'))
    return render_template('detail_diagnosis.html')

@app.route('/final-confirmation', methods=['POST'])
def final_confirmation():
    answer = request.form.get('final_confirm')
    if answer == 'ya':
        history = session.get('history', [])
        ticket = save_solved_case(history)
        session.clear()
        return render_template('ticket.html', ticket=ticket)
    else:
        return redirect(url_for('feedback'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        ticket = request.form.get('ticket')
        comment = request.form.get('comment')
        save_feedback(ticket, comment)
        return "Terima kasih atas feedback anda!"
    return render_template('feedback.html')

@app.route('/ticket/<ticket>')
def load_ticket(ticket):
    history = get_history_by_ticket(ticket)
    if not history:
        return "Ticket tidak ditemukan"

    qa_history = []
    for idx, node_key in enumerate(history):
        node = NODES.get(node_key)
        if isinstance(node, dict):
            question = node.get('question', '')
            answer = None
            if idx + 1 < len(history):
                next_key = history[idx + 1]
                for a, n in node['options'].items():
                    if n == next_key:
                        answer = a
                        break
            qa_history.append({'question': question, 'answer': answer})
        elif isinstance(node, str):
            qa_history.append({'question': 'Hasil Diagnosa', 'answer': node})

    return render_template('ticket.html', ticket=ticket, qa_history=qa_history)

@app.route('/input-ticket', methods=['GET', 'POST'])
def input_ticket():
    error = None
    if request.method == 'POST':
        ticket = request.form.get('ticket')
        history = get_history_by_ticket(ticket)
        if history:
            # Redirect to the /ticket/<ticket> route
            return redirect(url_for('load_ticket', ticket=ticket))
        else:
            error = "Ticket tidak ditemukan."
    return render_template('input_ticket.html', error=error)

@app.route('/glossary/<term>')
def glossary(term):
    term = term.lower()
    desc = GLOSSARY.get(term)
    if not desc:
        return "Istilah tidak ditemukan"
    return render_template('glossary.html', term=term, description=desc)

if __name__ == '__main__':
    # Create DB tables if not exist
    with app.app_context():
        db.create_all()

    app.run(debug=True)
