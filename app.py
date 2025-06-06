from flask import Flask, session, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import string
import re
import os 
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
import json

load_dotenv()
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE SETUP ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diagnosis.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1"
token = os.getenv("GITHUB_TOKEN")

client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(token),
)

# --- MODELS ---
class SolvedCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket = db.Column(db.String(12), unique=True, nullable=False)
    history = db.Column(db.Text, nullable=False)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket = db.Column(db.String(12), nullable=False)
    comment = db.Column(db.Text, nullable=False)


# Struktur node Enhanced Multiway Decision Tree with Confirmation Layer
NODES = {
  "start": {
    "question": "Apakah nampak bercak pada padi?",
    "options": {
      "Ya": "node1",
      "Tidak": "node11"
    }
  },

  "node1": {
    "question": "Apa warna bercaknya?",
    "options": {
      "Abu-Abu/Hijau Keabuan": "node2",
      "Coklat/Karat": "node3",
      "Tidak ada satupun pada pilihan": "node14",
    }
  },

  "node14": {
      "question": "Apa warna bercaknya?",
      "options": {
       "Pucat/Coklat tua kemerahan": "solusi9",  #Bercak cokelat sempit
       "Orange": "solusi10",  # Gosong palsu
       "Hitam": "solusi11",  # Stem rot  
  }
  },

  "node2": {
    "question": "Apa bentuk bercaknya?",
    "options": {
      "Oval/Elips": "solusi1",  # Rice Sheath Blight
      "Belah ketupat": "solusi2",  # Blast
      "Garis": "solusi3",  # Red stripe / Daun merah
      "Tidak ada di pilihan": "node8"
    }
  },

  "node3": {
    "question": "Apakah daun padi berlekuk, sobek, atau memiliki tepi tidak rata?",
    "options": {
      "Ya, daun berlekuk dan sobek": "solusi6",  # Rumput Kerdil
      "Tidak, daun tidak berlekuk dan sobek": "solusi7"  # Bercak Coklat
    }
  },

  "node8": {
    "question": "Apakah di sekeliling bercak terdapat warna kekuningan?",
    "options": {
      "Ya, terdapat bercak kekuningan": "solusi4",  # Bercak Kresek
      "Tidak, bercak kekuningan tidak terlihat": "solusi5"  # Leaf Scald
    }
  },

  "node11": {
    "question": "Apakah tanaman tumbuh kerdil, dengan daun menggulung atau jumlah anakan sedikit?",
    "options": {
      "Ya, tanaman kerdil dan daun menggulung": "solusi12",  #Tungro
      "Tidak, daun tidak menggulung": "node12"
    }
  },

  "node12": {
    "question": "Apakah tanaman tumbuh lebih tinggi dari biasanya dan daunnya menguning?",
    "options": {
      "Ya, tumbuh tinggi dan daun menguning": "solusi13",  # Bakanae
      "Tidak, daun tidak menguning dan tumbuh normal": "node13"
    }
  },

  "node13": {
    "question": "Apakah terdapat gumpalan beludru pada bulir padi?",
    "options": {
      "Ya, ada gumpalan beludru": "solusi14",  # False Smut
      "Tidak, gumpalan tidak terlihat": "solusi15"  # Tidak teridentifikasi
    }
  },

  "solusi1": { "diagnosis": "Rice Sheath Blight",
              "confirmation_questions": [
    {
      "question": "Apakah bercak yang dalam kondisi baru berukuran 0.5-3mm?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah kondisi daun yang tergejala bercak dalam waktu lama mati lengkap?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah padi menjadi rebah dan pengisian bulir terhambat?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    }

  ] },

  "solusi2": { "diagnosis": "Blast",
              "confirmation_questions": [
    {
      "question": "Apakah bintik-bintik awal berukuran kecil dan basah karena air?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah jamur yang terlihat memiliki konidia dengan 2-septa (3-sel)?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.4,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah lesi menunjukkan pola khas dengan pusat abu-abu dikelilingi tepi coklat kemerahan?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    }

  ] },

  "solusi3": { "diagnosis": "Daun Merah",
              "confirmation_questions": [
    {
      "question": "Apakah lesi memanjang di sepanjang pelepah menuju daun membentuk strip-strip merah?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah dalam kasus parah menyebabkan rebah dan menghambat pengisian bulir?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.4,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah beberapa lesi besar pada pelepah menyebabkan kematian daun lengkap?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    }

  ]  },

  "solusi4": { "diagnosis": "Bercak Kresek (Bacterial Leaf Blight)",
              "confirmation_questions": [
    {
      "question": "Apakah serangan di awal pertumbuhan langsung menyebabkan tanaman layu dan mati?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah bercak berkembang menjadi hawar memanjang (blight) sebelum mengering?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.4,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah gejala dimulai dari bagian daun yang terluka atau tepi daun?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    }

  ]  },

  "solusi5": { "diagnosis": "Leaf Scald",
              "confirmation_questions": [
    {
      "question": "Apakah bercak menghasilkan pola zonasi bergantian antara coklat muda dan tua?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
    {
      "question": "Apakah daerah yang terkena dampak mengering atau melepuh?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
  ]   },

  "solusi6": { "diagnosis": "Rumput Kerdil (Rice Grassy Stunt Virus)",
              "confirmation_questions": [
    {
      "question": "Apakah tanaman menunjukkan pertumbuhan terhambat (kerdil)?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah daun berwarna hijau gelap dengan tepi tidak rata?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
        {
      "question": "Apakah ujung daun terpilin dengan pembengkakan tulang daun?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    }
  ]   },

  "solusi7": { "diagnosis": "Bercak Coklat (Brown Spot)",
              "confirmation_questions": [
    {
      "question": "Apakah pada varietas resisten, luka hanya seukuran kepala peniti?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
    {
      "question": "Apakah saat bercak membesar terlihat pusat abu-abu di tengah dengan tepian coklat kemerahan?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
  ]  },

  "solusi9": { "diagnosis": "Bercak Coklat Sempit (Narrow Brown Leaf Spot)",
              "confirmation_questions": [
    {
      "question": "Apakah lebar bercak konsisten sekitar 1-1,5 mm?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah area pinggir bercak terlihat lebih pucat dari bagian tengah?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
      {
      "question": "Apakah serangan menyebabkan pematangan biji lebih cepat dari normal?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
  ]   },

  "solusi10": { "diagnosis": "Gosong Palsu (Ustilaginoidea virens)",
               "confirmation_questions": [
    {
      "question": "Apakah serbuk kuning mudah buyar dan menempel pada pakaian?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
    {
      "question": "Apakah hanya sebagian bulir yang terkena, bukan seluruh malai?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
  ]    },

  "solusi11": { "diagnosis": "Stem Rot",
                "confirmation_questions": [
    {
      "question": "Apakah lesi membesar menembus pelepah dalam dan batang menjadi hitam kecoklatan?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
    {
      "question": "Apakah batang keabu-abuan, berlubang, dan akhirnya roboh?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
  ]  },
  
  "solusi12": { "diagnosis": "Tungro",
               "confirmation_questions": [
    {
      "question": "Apakah jumlah anakan sedikit saat fase vegetatif?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
    {
      "question": "Apakah daun muda agak menggulung?",
      "options": {
        "Ya": 0.5,
        "Tidak": 0.25,
        "Tidak Tahu": 0.3
      }
    },
  ] },

  "solusi13": { "diagnosis": "Bakanae",
              "confirmation_questions": [
    {
      "question": "Apakah gejala pertama terlihat setelah 5 hari semai?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah tanaman menghasilkan biji kosong dan berubah warna meski pertumbuhan normal?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah daun terinfeksi menjadi lebih tipis dibanding tanaman sehat?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
  ]  },

  "solusi14": { "diagnosis": "False Smut",
               "confirmation_questions": [
    {
      "question": "Apakah terdapat gumpalan bulat berwarna orange seperti beludru berdiameter 1 cm?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah bagian bunga tertutup membran keputihan?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
    {
      "question": "Apakah gumpalan berubah menjadi hijau kekuningan atau hitam kehijauan saat mengering?",
      "options": {
        "Ya": 0.33,
        "Tidak": 0.16,
        "Tidak Tahu": 0.2
      }
    },
  ] },

  "solusi15": { "diagnosis": "Tidak dapat diidentifikasi dengan gejala yang diberikan" }
}


# GLOSSARY buat kata kunci yang susah dimengerti oleh petani
GLOSSARY = {
    "blast": {
        "desc": "Blast adalah penyakit pada padi yang disebabkan oleh jamur Pyricularia oryzae.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-leaf-collar"
    },
    "tungro": {
        "desc": "Tungro adalah penyakit virus yang ditularkan oleh wereng hijau.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/tungro"
    },
    "false smut": {
        "desc": "Bercak adalah tanda gejala penyakit pada daun berupa noda atau perubahan warna.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/false-smut"
    },
    "rice sheath blight": {
        "desc": "Rice Sheath Blight adalah penyakit yang disebabkan oleh jamur Rhizoctonia solani, ditandai dengan bercak coklat pada pelepah daun.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/sheath-blight"
    },
    "bacterial leaf blight": {
        "desc": "Bacterial Leaf Blight adalah penyakit yang disebabkan oleh bakteri Xanthomonas oryzae pv. oryzae, ditandai dengan bercak air pada daun.",
        "wiki": "http://www.knowledgebank.irri.org/decision-tools/rice-doctor/rice-doctor-fact-sheets/item/bacterial-blight"
    },
    "bakanae": {
        "desc": "Bakanae adalah penyakit jamur yang disebabkan oleh Fusarium moniliforme, ditandai dengan tanaman kerdil dan daun kuning.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/bakanae"
    },
    "leaf scald": {
        "desc": "Leaf Scald adalah penyakit yang disebabkan oleh bakteri, ditandai dengan daun menguning dan layu.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/leaf-scald"
    },
    "brown spot": {
        "desc": "Brown Spot adalah penyakit yang disebabkan oleh jamur Bipolaris oryzae, ditandai dengan bercak coklat pada daun.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/brown-spot"
    },
    "narrow brown leaf spot": {
        "desc": "Narrow Brown Leaf Spot adalah penyakit yang disebabkan oleh jamur Cercospora janseana, ditandai dengan bercak coklat sempit pada daun.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/narrow-brown-spot"
    },
    "rice grassy stunt virus": {
        "desc": "Rice Grassy Stunt Virus adalah penyakit virus yang ditularkan oleh wereng, ditandai dengan tanaman kerdil dan daun menggulung.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/rice-grassy-stunt"
    },
    "stem rot": {
        "desc": "Stem Rot adalah penyakit yang disebabkan oleh jamur Sclerotium oryzae, ditandai dengan pembusukan batang padi.",
        "wiki": "http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/stem-rot"
    },
    # Glosarium tambahan 1–50
    "trichoderma harzianum": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Trichoderma_harzianum"},
    "trichoderma viride": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Trichoderma_viride"},
    "carbendazim": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Carbendazim"},
    "propiconazole": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Propiconazole"},
    "validamycin": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Validamycin"},
    "chlorothalonil": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Chlorothalonil"},
    "edifenphos": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Edifenphos"},
    "bacillus subtilis": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Bacillus_subtilis"},
    "pseudomonas fluorescens": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Pseudomonas_Fluorescens"},
    "triflumizole": {"desc": "", "wiki": "https://de.wikipedia.org/wiki/Triflumizol"},
    "streptomyces": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Streptomyces"},
    "budidaya": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Budi_daya"},
    "bakteri": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Bakteri"},
    "antibiotic": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Antibiotic"},
    "irigasi": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Irigasi"},
    "pathogen": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Patogen"},
    "varietas": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Varietas_(botani)"},
    "fungisida": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Fungisida"},
    "konidia": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Konidium"},
    "metil tiopanat": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Thiophanate-methyl"},
    "kalium": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Kalium"},
    "nitrogen": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Nitrogen"},
    "beludru": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Beludru"},
    "lesi": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Lesi"},
    "drainase": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Drainase"},
    "malai": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Malai"},
    "insektisida": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Insektisida"},
    "benih": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Benih"},
    "hayati": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Biologi"},
    "corynebacterium": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Corynebacterium"},
    "bakterisida": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Bakterisida"},
    "oryza sativa": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Oryza_sativa"},
    "terinfeksi": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Terinfeksi"},
    "matang": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Keranuman"},
    "paenibacilus polymyxa": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Paenibacillus_polymyxa"},
    "membrane": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Membrane"},
    "hipoklorit": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Hipoklorit"},
    "senyawa": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Senyawa"},
    "vegetasi": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Vegetasi"},
    "mankozeb": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Mancozeb"},
    "bulir": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Kerohi"},
    "flora mikro": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Flora_(microbiology)"},
    "tebuconazole": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Tebuconazole"},
    "jamur": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Jamur"},
    "ustilago": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Ustilago"},
    "benzimidazole": {"desc": "", "wiki": "https://en.wikipedia.org/wiki/Benzimidazole"},
    "triazol": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Triazola"},
    "sanitasi": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Sanitasi"},
    "gulma": {"desc": "", "wiki": "https://id.wikipedia.org/wiki/Gulma"}
}


# Tambahkan solusi detail untuk setiap penyakit
SOLUSI_DETAIL = {
    "Rice Sheath Blight": """
    <h3>Solusi Kimiawi:</h3>
    <ul>
        <li>Gunakan fungisida foliar: Carbendazim (1g/lit) dan Propiconazole (1ml/lit) sangat efektif</li>
        <li>Penyemprotan fungisida seperti Benomyl dan Iprodione serta antibiotik Validamycin</li>
        <li>Chlorothalonil 1 kg atau Edifenphos 1 lit/ha untuk tanaman terinfeksi</li>
    </ul>
    <h3>Solusi Biologis:</h3>
    <ul>
        <li>Bacillus subtilis MBI 600 (22.9%)</li>
        <li>Pseudomonas Fluorescens Strain 7-14 (85%)</li>
        <li>Marine associated AMET1102, AMET1104, AMET1133 (31.9%)</li>
        <li>Streptomyces PM5 (82.3%)</li>
        <li>Trichoderma harzianum 4-8 gram (70%)</li>
        <li>Trichoderma viride (45.70–47.30%)</li>
    </ul>
    <h3>Solusi Budidaya:</h3>
    <ul>
        <li>Terapkan pupuk hijau 6,25 t/ha atau FYM 12,5 t/ha</li>
        <li>Hindari penggunaan pupuk berlebihan dan jaga jarak tanam optimal</li>
        <li>Hindari aliran air irigasi dari ladang terinfeksi</li>
        <li>Lakukan pembajakan dalam dan pembakaran jerami</li>
    </ul>
    """,
    
    "Blast": """
    <h3>Pengendalian Budidaya:</h3>
    <ul>
        <li>Jaga jarak tanam tidak terlalu rapat atau gunakan sistem legowo</li>
        <li>Pilih varietas tahan: Inpari 21, 22, 26, 27, Inpago 4, 5, 6, 7, 8</li>
    </ul>
    <h3>Pengendalian Kimiawi:</h3>
    <ul>
        <li>Gunakan fungisida Envoy 80 WP (mancozeb + trisiklazol) untuk blast daun dan potong leher</li>
    </ul>
    <h3>Pemupukan:</h3>
    <ul>
        <li>Gunakan pupuk nitrogen dan kalium secara berimbang</li>
        <li>Hindari pupuk nitrogen berlebihan yang meningkatkan keparahan penyakit</li>
    </ul>
    """,

    "Daun Merah (Red Stripe)": """
    <h3>Pengendalian Budidaya:</h3>
    <ul>
        <li>Tanam varietas yang tahan</li>
        <li>Pastikan ruang cukup antara tanaman dan jumlah penyemaian optimal</li>
        <li>Pantau lahan secara teratur untuk deteksi dini</li>
        <li>Jangan memberi pupuk nitrogen berlebihan</li>
        <li>Atur drainase berjeda</li>
    </ul>
    """,

    "Bercak Kresek (Bacterial Leaf Blight)": """
    <h3>Pengendalian Terpadu:</h3>
    <ul>
        <li>Cek keadaan tanah, pengairan, pemupukan, kelembaban, suhu dan ketahanan varietas</li>
    </ul>
    <h3>Perbaikan Budidaya:</h3>
    <ul>
        <li>Pengolahan tanah optimal</li>
        <li>Pengaturan pola tanam dan waktu tanam serempak</li>
        <li>Pergiliran tanam dan varietas tahan</li>
        <li>Penanaman varietas unggul dari benih sehat</li>
        <li>Pengaturan jarak tanam</li>
        <li>Pemupukan berimbang (N, P, K dan unsur mikro)</li>
        <li>Pengaturan sistem pengairan sesuai fase pertumbuhan</li>
    </ul>
    <h3>Pengendalian Biologis:</h3>
    <ul>
        <li>Pemanfaatan agensia hayati Corynebacterium</li>
        <li>Gunakan bakteri Paenibacilus polymyxa Mace</li>
    </ul>
    <h3>Pengendalian Kimiawi:</h3>
    <ul>
        <li>Penyemprotan bakterisida yang efektif berdasarkan pengamatan</li>
    </ul>
    """,

    "Leaf Scald": """
    <h3>Pengendalian Kimiawi:</h3>
    <ul>
        <li>Perendaman benih dengan metil tiofanat untuk mengurangi infeksi</li>
        <li>Semprotan daun dengan fungisida mengandung mancozeb, metil tiofonat</li>
    </ul>
    <h3>Pengendalian Budidaya:</h3>
    <ul>
        <li>Gunakan varietas tahan penyakit</li>
        <li>Perbesar jarak antar tanaman</li>
        <li>Pertahankan kadar silicon tinggi di tanah</li>
        <li>Hindari kadar nitrogen berlebihan saat pemupukan</li>
    </ul>
    """,

    "Rumput Kerdil (Rice Grassy Stunt Virus)": """
    <h3>Pengendalian:</h3>
    <ul>
        <li>Musnahkan inang/tanaman sakit secara selektif</li>
        <li>Lebarkan jarak tanam agar sinar matahari cukup</li>
        <li>Gunakan varietas tahan serangan</li>
        <li>Gunakan pupuk secara wajar</li>
        <li>Pantau lahan secara teratur untuk deteksi tanda-tanda serangan</li>
    </ul>
    """,

    "Bercak Coklat (Brown Spot)": """
    <h3>Manajemen Kimia:</h3>
    <ul>
        <li>Aplikasi fungisida sintetis melalui perawatan benih dan daun</li>
        <li>Propikonazol (triazol) sebagai produk paling efektif untuk perawatan daun</li>
    </ul>
    <h3>Manajemen Biologis:</h3>
    <ul>
        <li>Ekstrak tanaman Nimba (Azadirachta indica)</li>
        <li>Penggunaan jamur dan bakteri antagonis</li>
    </ul>
    <h3>Manajemen Budidaya:</h3>
    <ul>
        <li>Jaga kelembaban tanah yang baik</li>
        <li>Pemusnahan inang alternatif dan sisa tanaman terinfeksi</li>
        <li>Gunakan benih sehat</li>
        <li>Keseimbangan unsur mikro dan makro di tanah</li>
    </ul>
    """,

    "Bercak Coklat Sempit (Narrow Brown Leaf Spot)": """
    <h3>Pengendalian:</h3>
    <ul>
        <li>Gunakan varietas yang lebih tahan jika tersedia</li>
        <li>Singkirkan gulma dan tanaman liar di lahan sekitar</li>
        <li>Perencanaan pemupukan berimbang sepanjang musim</li>
        <li>Pastikan tolak ukur kalium saat penggunaan agar lebih dari cukup</li>
    </ul>
    """,

    "Gosong Palsu (Ustilaginoidea virens)": """
    <h3>Pengendalian Preventif:</h3>
    <ul>
        <li>Gunakan fungisida protektif yang bekerja secara kontak</li>
        <li>Fungisida golongan ditiokarbamat: ziram, maneb, zineb, mancozeb, metiram, propineb</li>
    </ul>
    <h3>Pengendalian Kuratif:</h3>
    <ul>
        <li>Fungisida golongan Metoksi Akrilat, Tiofanat, Benzimidazol, Triazol</li>
        <li>Bahan aktif azoksistrobin (Amistartop, Tandem) atau trifloksistrobin</li>
    </ul>
    """,

    "Stem Rot": """
    <h3>Pengendalian Budidaya:</h3>
    <ul>
        <li>Kurangi kepadatan saat penanaman</li>
        <li>Keringkan lahan untuk mengurangi penyebaran jamur</li>
        <li>Tingkatkan kandungan kalium untuk menjaga pH tanah tinggi</li>
        <li>Bakar semua sisa tanaman setelah panen, jangan biarkan jerami membusuk</li>
        <li>Hindari genangan air irigasi</li>
        <li>Bajak hingga sisa tanaman terkubur jauh di dalam tanah</li>
        <li>Biarkan lahan kosong (bera) selama beberapa bulan atau satu tahun</li>
        <li>Kendalikan gulma di dalam dan sekitar lahan</li>
        <li>Jangan melukai tanaman selama pekerjaan di lahan</li>
    </ul>
    """,

    "Tungro": """
    <h3>Pengendalian:</h3>
    <ul>
        <li>Tanam serempak untuk memutus siklus hidup vektor dan memperpendek waktu keberadaan sumber inokulum</li>
        <li>Atur waktu tanam tepat berdasarkan pola fluktuasi populasi wereng hijau</li>
        <li>Fase pertumbuhan padi peka tungro pada umur kurang dari 45 hari setelah tanam</li>
        <li>Tanam sejajar legowo</li>
        <li>Gunakan varietas tahan wereng hijau</li>
        <li>Aplikasi insektisida untuk mengendalikan vektor</li>
    </ul>
    """,

    "Bakanae": """
    <h3>Pengendalian:</h3>
    <ul>
        <li>Gunakan air dan garam untuk memisahkan benih terinfeksi ringan dari yang sehat</li>
        <li>Pertimbangkan perlakukan hayati jika tersedia</li>
        <li>Rendam benih dalam fungisida mengandung trifumizole, propikonazol, prokloraz selama 5 jam</li>
        <li>Perlakuan benih dengan natrium hipoklorit (pemutih)</li>
        <li>Penyemprotan senyawa fungisida 2 kali pada tahap vegetatif dengan interval mingguan</li>
    </ul>
    """,

    "False Smut": """
    <h3>Pengendalian:</h3>
    <ul>
        <li>Gunakan benih sehat dari penjual asli dan bersertifikat</li>
        <li>Lakukan pembasahan dan pengeringan lahan bergantian daripada penggenangan permanen</li>
        <li>Pengolahan tanah konservasi dan penanaman padi berkelanjutan</li>
        <li>Rotasi tanaman 2–3 tahun dengan tanaman tidak rentan</li>
        <li>Jaga kebersihan tanggul lahan dan saluran irigasi</li>
        <li>Gunakan nitrogen secukupnya dalam beberapa kali pemberian</li>
        <li>Pantau secara berkala</li>
        <li>Fungisida: Trioxystrobin 25%, Tebuconazole 50%, Propiconazole 25 EC</li>
    </ul>
    """,

    "Tidak dapat diidentifikasi dengan gejala yang diberikan": """
    <h3>Rekomendasi:</h3>
    <ul>
        <li>Konsultasikan dengan ahli pertanian atau penyuluh pertanian setempat</li>
        <li>Lakukan pemeriksaan laboratorium untuk identifikasi patogen</li>
        <li>Ambil sampel tanaman terinfeksi untuk analisis lebih lanjut</li>
        <li>Hubungi dinas pertanian setempat untuk bantuan teknis</li>
        <li>Dokumentasikan gejala dengan foto untuk konsultasi</li>
    </ul>
    """
}


# --- HELPERS ---

def generate_ticket():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def highlight_glossary(text):
    if not isinstance(text, str):
        return text
    def repl(m):
        word = m.group(0)
        word_lc = word.lower()
        if word_lc in GLOSSARY:
            wiki_url = GLOSSARY[word_lc]["wiki"]
            return f'<a href="{wiki_url}" target="_blank" class="glossary-link">{word}</a>'
        return word
    pattern = re.compile('|'.join(re.escape(k) for k in GLOSSARY.keys()), re.IGNORECASE)
    return pattern.sub(repl, text)

def save_solved_case(history):
    ticket = generate_ticket()
    # Simpan history sebagai JSON string
    history_str = json.dumps(history)
    new_case = SolvedCase(ticket=ticket, history=history_str)
    db.session.add(new_case)
    db.session.commit()
    return ticket

def get_history_by_ticket(ticket):
    case = SolvedCase.query.filter_by(ticket=ticket).first()
    if case:
        try:
            return json.loads(case.history)
        except Exception:
            # fallback ke format lama (comma separated string)
            return case.history.split(',')
    return None

def save_feedback(ticket, comment):
    new_feedback = Feedback(ticket=ticket, comment=comment)
    db.session.add(new_feedback)
    db.session.commit()


def calculate_confidence_score(solution_key, answers):
    solution = NODES[solution_key]
    questions = solution.get('confirmation_questions', [])
    total = 0
    for idx, ans in enumerate(answers):
        if idx < len(questions):
            weight = questions[idx]['options'].get(ans, 0)
            total += weight
    return round(total * 100, 2)  # sum as percentage

# --- ROUTES ---
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    try:
        response = client.complete(
            messages=[
                SystemMessage("Anda adalah seorang ahli botani dan pakar agronomi spesialis penyakit tanaman padi.Tugas Anda adalah membantu pengguna mendiagnosis penyakit tanaman padi berdasarkan gejala yang mereka sampaikan, serta memberikan saran atau solusi penanganan yang tepat, termasuk tindakan pencegahan dan pengobatan. Hanya jawab pertanyaan yang berkaitan dengan penyakit padi, gejala, penanganan, dan pencegahannya.Tolak dengan sopan jika ada pertanyaan di luar topik tersebut. Gunakan bahasa yang jelas, ringkas, dan mudah dipahami oleh petani atau pengguna umum. Jika gejala kurang lengkap, arahkan pengguna untuk menjelaskan lebih rinci.Contoh jawaban jika pertanyaan di luar topik: Maaf, saya hanya dapat membantu terkait penyakit tanaman padi dan penanganannya. Silakan ajukan pertanyaan sesuai topik tersebut."),
                UserMessage(user_message)
            ],
            temperature=0.7,
            top_p=1,
            model=model
        )
        answer = response.choices[0].message.content
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    # Jika node adalah solusi dengan confirmation_questions
    if isinstance(node, dict) and 'diagnosis' in node:
        confirmation_answers = session.get('confirmation_answers', [])
        questions = node.get('confirmation_questions', [])
        if len(confirmation_answers) < len(questions):
            # Tampilkan pertanyaan konfirmasi berikutnya
            q = questions[len(confirmation_answers)]
            if request.method == 'POST':
                answer = request.form.get('answer')
                confirmation_answers.append(answer)
                session['confirmation_answers'] = confirmation_answers
                # Simpan ke history juga
                if 'confirmation_history' not in session:
                    session['confirmation_history'] = []
                session['confirmation_history'].append({
                    'question': q['question'],
                    'answer': answer
                })
                return redirect(url_for('diagnosis'))
            return render_template('question.html', question=q['question'], options=q['options'].keys())
        else:
            # Semua pertanyaan konfirmasi sudah dijawab, hitung skor
            confidence = calculate_confidence_score(current, confirmation_answers)
            diagnosis_name = node['diagnosis']
            highlighted = highlight_glossary(diagnosis_name)
            solusi = SOLUSI_DETAIL.get(diagnosis_name, "Solusi belum tersedia.")
            solusi_highlighted = highlight_glossary(solusi)
            # Simpan confirmation_history ke history utama sebelum reset
            if 'confirmation_history' in session:
                for item in session['confirmation_history']:
                    history.append({'confirmation': True, 'question': item['question'], 'answer': item['answer']})
                session.pop('confirmation_history')
                session['history'] = history
            session.pop('confirmation_answers', None)
            return render_template('result.html', result=highlighted, solusi=solusi_highlighted, confidence=confidence)

    # Jika node adalah solusi string (lama)
    if isinstance(node, str):
        highlighted = highlight_glossary(node)
        solusi = SOLUSI_DETAIL.get(node, "Solusi belum tersedia.")
        solusi_highlighted = highlight_glossary(solusi)
        return render_template('result.html', result=highlighted, solusi=solusi_highlighted)

    # Jika node pertanyaan biasa
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
            return redirect(url_for('chatbot'))
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
        # Jika item adalah dict (confirmation question)
        if isinstance(node_key, dict) and node_key.get('confirmation'):
            qa_history.append({'question': node_key['question'], 'answer': node_key['answer']})
        else:
            node = NODES.get(node_key)
            if isinstance(node, dict):
                question = node.get('question', '')
                answer = None
                if idx + 1 < len(history):
                    next_key = history[idx + 1]
                    # skip if next_key is confirmation dict
                    if isinstance(next_key, dict):
                        continue
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
    glossary_entry = GLOSSARY.get(term)
    if glossary_entry:
        return render_template('glossary.html', term=term, description=glossary_entry['desc'], wiki=glossary_entry['wiki'])
    else:
        return f"<h3>Istilah '{term}' tidak ditemukan dalam glossary.</h3>", 404

if __name__ == '__main__':
    # Create DB tables if not exist
    with app.app_context():
        db.create_all()

    app.run(debug=True)
