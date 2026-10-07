"""Общие настройки проекта: пути, группы нейронов, параметры симуляции.

Все названия типов нейронов взяты из аннотаций FlyWire (Schlegel et al., Nature 2024,
репозиторий flyconnectome/flywire_annotations, релиз 783).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
LITERATURE = ROOT / "data" / "literature"
MODELS = ROOT / "models"
WEB = ROOT / "web"

ZENODO_CONNECTIONS = "https://zenodo.org/records/10676866/files/proofread_connections_783.feather?download=1"
ZENODO_SKELETONS = "https://zenodo.org/records/10877326/files/sk_lod1_783_healed_ds2.parquet?download=1"
ANNOTATIONS_URL = ("https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/"
                   "supplemental_files/Supplemental_file1_neuron_annotations.tsv")

# --- Симуляция -----------------------------------------------------------------------
DT_MS = 5.0          # шаг интегрирования, мс
T_STEPS = 300        # 300 * 5 мс = 1.5 с одного «эпизода ухаживания»
STIM_ON = 20         # стимул начинается через 100 мс
READOUT_FROM = 180   # решение считывается по средней активности в последние 0.6 с
MIN_SYN = 5          # порог синапсов для связи (стандарт FlyWire)

# --- Функциональные группы нейронов самки ------------------------------------------
# Синонимы из литературы указаны в колонке `synonyms` таблицы аннотаций FlyWire.
PC2L_TYPES = ["AVLP567", "AVLP568", "AVLP569", "AVLP570", "CL313", "SIP200f", "SIP201f"]
PCD_TYPES = ["CB0975", "CB1379", "CB1390", "CB1508", "CB1930", "CB2021", "CB2138", "CB2284",
             "CB2520", "CB3270", "CB3529", "CB0094", "CB0405", "CB2608", "CB3505", "CB3591",
             "SMP285", "SMP286"]

# Порядок важен: нейрон получает первую подходящую группу.
FEMALE_GROUPS = [
    # key, условие отбора, русское название, роль
    ("vpoDN", lambda t: t == "DNp37", "vpoDN — команда «принять самца»",
     "Нисходящие нейроны, открывающие вагинальную пластинку (Wang et al., 2021)."),
    ("DNp13", lambda t: t == "DNp13", "DNp13 — команда «отказ»",
     "Нисходящие нейроны выдвижения яйцеклада — сигнал отказа (Wang et al., 2020)."),
    ("vpoEN", lambda t: t == "vpoEN", "vpoEN — детектор песни своего вида",
     "Слуховые нейроны, настроенные на межимпульсный интервал ~35 мс (Wang et al., 2021)."),
    ("pC1", lambda t: t in ("pC1a", "pC1b", "pC1c"), "pC1a-c — «центр желания»",
     "Нейроны doublesex, объединяющие песню, феромон cVA и статус спаривания (Zhou et al., 2014)."),
    ("pC1de", lambda t: t in ("pC1d", "pC1e"), "pC1d/e — социальное возбуждение",
     "Нейроны устойчивого внутреннего состояния, агрессия самки (Deutsch et al., 2020)."),
    ("pC2l", lambda t: t in PC2L_TYPES, "pC2l — детекторы песни",
     "Нейроны doublesex, реагирующие на импульсную песню (Deutsch et al., 2019)."),
    ("pCd", lambda t: t in PCD_TYPES, "pCd — феромонный вход",
     "Нейроны doublesex, отвечающие на феромон cVA (Zhou et al., 2014)."),
    ("SAG", lambda t: t == "AN_SMP_2", "SAG — сигнал «я девственница»",
     "Восходящие нейроны от половых путей; молчат после спаривания (Feng et al., 2014)."),
    ("vpoIN", lambda t: t == "AVLP008", "AVLP008 — тормозной вход vpoDN",
     "ГАМК-ергические нейроны (aSP-k), второй по силе вход в vpoDN по коннектому FlyWire."),
    ("aSP", lambda t: t.startswith("aSP-g") or t.startswith("aSP-f"), "aSP-f/g — феромоны в латеральном роге",
     "Нейроны fruitless латерального рога, обрабатывающие cVA (Kohl et al., 2013)."),
    ("PN_cVA", lambda t: t in ("DA1_lPN", "DA1_vPN", "DL3_lPN"), "Проекционные нейроны cVA",
     "Передают запах cVA из антеннальной доли (клубочки DA1 и DL3)."),
    ("ORN_cVA", lambda t: t in ("ORN_DA1", "ORN_DL3"), "Обонятельные нейроны Or67d/Or65a",
     "Рецепторы феромона самца цис-вакценилацетата (Kurtovic et al., 2007)."),
    ("JO", lambda t: t.startswith("JO-A") or t.startswith("JO-B"), "Слух: Джонстонов орган",
     "Механосенсорные нейроны антенны, чувствительные к звуку песни (Kamikouchi et al., 2009)."),
]
FEMALE_KEY_GROUPS = [g[0] for g in FEMALE_GROUPS]
SENSORY_GROUPS = {"JO", "ORN_cVA", "SAG"}

# Группы, которые можно «выключить/включить» (виртуальная оптогенетика)
MANIPULABLE = ["vpoDN", "DNp13", "vpoEN", "pC1", "pC1de", "pC2l", "pCd", "SAG", "vpoIN", "aSP"]

# --- Самец: коннектом MaleCNS (Berg et al., Cell 2026), полная ЦНС: мозг + брюшная нервная цепочка ---
RAW_MALE = RAW / "male"
MALECNS_BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0"
MALECNS_FILES = [
    "connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "connectome-data/flat-connectome/body-neurotransmitters-male-cns-v1.0.feather",
    "connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather",
]
MALECNS_SKELETONS = MALECNS_BASE + "/segmentation/skeletons-malecns/skeletons-precomputed"

ASP_M_TYPES = ["AVLP700m", "AVLP704m", "AVLP727m", "AVLP750m", "aSP-g3Am",
               "AVLP753m", "LH001m", "LH002m", "LH003m", "LH006m", "LH008m", "PVLP205m"]
MALE_GROUPS = [
    ("P1", lambda t: t.startswith("pC1_"), "P1 — центр решения ухаживать",
     "Мужские нейроны fruitless/doublesex: объединяют феромоны и зрение и запускают ухаживание (Kimura et al., 2008; Kohatsu et al., 2011)."),
    ("pIP10", lambda t: t == "pIP10", "pIP10 — команда «петь»",
     "Нисходящий нейрон песни ухаживания (von Philipsborn et al., 2011)."),
    ("song", lambda t: t in ("vPR6", "dPR1") or t.startswith("TN1a"), "Генератор песни в нервной цепочке",
     "Нейроны vPR6, dPR1, TN1A в грудных ганглиях, задающие ритм песни крыльями."),
    ("vAB3", lambda t: t in ("AN09B017e", "AN09B017f", "AN09B017g"), "vAB3 — «рядом самка»",
     "Восходящие нейроны, возбуждаемые феромонами самки; возбуждают P1 (Clowney et al., 2015)."),
    ("PPN1", lambda t: t == "AN05B102a", "PPN1 — феромонный вход P1",
     "Восходящие нейроны от вкусовых клеток ног, активируют P1 (Kallman et al., 2015)."),
    ("mAL", lambda t: t.startswith("mAL_m"), "mAL — торможение P1",
     "Мужские ГАМК-ергические нейроны, тормозящие P1 при запахе соперника (Kallman et al., 2015)."),
    ("aSP", lambda t: t in ASP_M_TYPES, "aSP-f/g — феромоны в латеральном роге",
     "Мужские нейроны fruitless, обрабатывающие феромон cVA."),
    ("PN_cVA", lambda t: t in ("DA1_lPN", "DA1_vPN", "M_lvPNm43", "M_lvPNm45"), "Проекционные нейроны cVA",
     "Передают запах cVA из клубочка DA1."),
    ("ORN_cVA", lambda t: t == "ORN_DA1", "Обонятельные нейроны Or67d",
     "Чувствуют cVA — запах самца, оставшийся и на спарившейся самке (Kurtovic et al., 2007)."),
    ("GRN_F", lambda t: t in ("LgLG1b", "LgLG5", "LgLG8"), "Вкус ног: феромон самки",
     "Клетки ppk23/ppk25 на лапках, чувствуют 7,11-гептакозадиен самки (F-клетки, Kallman et al., 2015)."),
    ("GRN_M", lambda t: t in ("LgLG1a", "LgLG6", "LgLG7"), "Вкус ног: феромон самца",
     "Клетки ppk23 на лапках, чувствуют 7-трикозен самцов (M-клетки, Thistle et al., 2012)."),
    ("LC10a", lambda t: t == "LC10a", "Зрение: LC10a",
     "Зрительные нейроны, следящие за движущейся целью при ухаживании (Ribeiro et al., 2018)."),
]
MALE_SENSORY_GROUPS = {"GRN_F", "GRN_M", "ORN_cVA", "LC10a"}
MALE_MANIPULABLE = ["P1", "pIP10", "song", "vAB3", "PPN1", "mAL", "aSP", "LC10a"]
