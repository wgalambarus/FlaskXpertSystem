from flask import Flask, session, request, render_template, redirect, url_for
import random
import string
import re

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Expert system decision tree example
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


# Glosarium istilah untuk highlight
GLOSSARY = {
    "power supply": "Perangkat yang memasok daya listrik ke komputer.",
    "monitor": "Perangkat output visual untuk komputer.",
    "sistem operasi": "Perangkat lunak yang mengatur hardware dan software komputer."
}

# Data penyimpanan sementara (bisa diganti DB)
solved_cases = {}
feedbacks = {}

def generate_ticket():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def highlight_glossary(text):
    # Highlight kata glosarium jadi link ke glossary page
    def repl(m):
        word = m.group(0).lower()
        if word in GLOSSARY:
            return f'<a href="{url_for("glossary", term=word)}" class="glossary-link">{word}</a>'
        return word

    pattern = re.compile('|'.join(re.escape(k) for k in GLOSSARY.keys()), re.IGNORECASE)
    return pattern.sub(repl, text)

@app.route('/start-diagnosis')
def start_diagnosis():
    session.clear()  # reset semua session agar diagnosis benar-benar baru
    session['history'] = ['start']
    return redirect(url_for('diagnosis'))

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        ticket_input = request.form.get('ticket_input', '').strip()
        if ticket_input:
            if ticket_input in solved_cases:
                history = solved_cases[ticket_input]
                # Tampilkan riwayat pertanyaan & jawaban diagnosa berdasarkan history
                qa_history = []
                for node_key in history:
                    node = NODES.get(node_key)
                    if isinstance(node, dict):
                        question = node.get('question', '')
                        # cari jawaban yang menuju node_key berikutnya
                        idx = history.index(node_key)
                        if idx + 1 < len(history):
                            next_key = history[idx+1]
                            # cari jawaban user yang membawa ke next_key
                            answer = None
                            for a, n in node['options'].items():
                                if n == next_key:
                                    answer = a
                                    break
                        else:
                            answer = None
                        qa_history.append({'question': question, 'answer': answer})
                    elif isinstance(node, str):
                        # solusi terakhir
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

    # Cek dulu apakah node adalah string (berarti solusi akhir)
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
        ticket = generate_ticket()
        solved_cases[ticket] = history.copy()
        session.clear()  # bersihkan setelah selesai
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
        # Bisa simpan detail jawaban di session jika mau
        session['detail_answer'] = answer
        return redirect(url_for('final_confirm'))
    return render_template('detail_diagnosis.html')

@app.route('/final-confirmation', methods=['POST'])
def final_confirmation():
    answer = request.form.get('final_confirm')
    if answer == 'ya':
        history = session.get('history', [])
        ticket = generate_ticket()
        solved_cases[ticket] = history.copy()
        session.clear()
        return render_template('ticket.html', ticket=ticket)
    else:
        return redirect(url_for('feedback'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        ticket = request.form.get('ticket')
        comment = request.form.get('comment')
        feedbacks[ticket] = comment
        return "Terima kasih atas feedback anda!"
    return render_template('feedback.html')

@app.route('/ticket/<ticket>')
def load_ticket(ticket):
    history = solved_cases.get(ticket)
    if not history:
        return "Ticket tidak ditemukan"
    # Bisa tampilkan detail history/hasil
    return render_template('ticket.html', ticket=ticket, history=history)
@app.route('/input-ticket', methods=['GET', 'POST'])
def input_ticket():
    if request.method == 'POST':
        ticket = request.form.get('ticket')
        if ticket in solved_cases:
            history = solved_cases[ticket]
            return render_template('ticket.html', ticket=ticket, history=history)
        else:
            error = "Ticket tidak ditemukan."
            return render_template('input_ticket.html', error=error)
    return render_template('input_ticket.html')

@app.route('/glossary/<term>')
def glossary(term):
    term = term.lower()
    desc = GLOSSARY.get(term)
    if not desc:
        return "Istilah tidak ditemukan"
    return render_template('glossary.html', term=term, description=desc)

if __name__ == '__main__':
    app.run(debug=True)
