"""Шаг 3б. Обучающая выборка для самца: ухаживает ли самец за целью и поёт ли он.

Поведение: «индекс ухаживания» — доля времени, которую самец ухаживает за целью (обычно за 10 мин),
и доля времени с песней крыльями. Как и для самки, значения заданы интервалами из статей.
Физиология: какие группы нейронов отвечают на какие сигналы (кальциевая визуализация).
Результат: data/literature/male_experiments.json
"""
import json

from config import LITERATURE

SRC = {
    "kurtovic2007": "Kurtovic A., Widmer A., Dickson B.J. (2007) A single class of olfactory neurons mediates behavioural responses to a Drosophila sex pheromone. Nature 446:542–546",
    "thistle2012": "Thistle R. et al. (2012) Contact chemoreceptors mediate male-male repulsion and male-female attraction during Drosophila courtship. Cell 149:1140–1151",
    "lu2012": "Lu B. et al. (2012) ppk23-dependent chemosensory functions contribute to courtship behavior in Drosophila melanogaster. PLoS Genet 8:e1002587",
    "toda2012": "Toda H., Zhao X., Dickson B.J. (2012) The Drosophila female aphrodisiac pheromone activates ppk23+ sensory neurons to elicit male courtship behavior. Cell Rep 1:599–607",
    "miyamoto2008": "Miyamoto T., Amrein H. (2008) Suppression of male courtship by a Drosophila pheromone receptor. Nat Neurosci 11:874–876",
    "wang2011": "Wang L. et al. (2011) Hierarchical chemosensory regulation of male-male social interactions in Drosophila. Nat Neurosci 14:757–762",
    "kallman2015": "Kallman B.R., Kim H., Scott K. (2015) Excitation and inhibition onto central courtship neurons biases Drosophila mate choice. eLife 4:e11188",
    "clowney2015": "Clowney E.J. et al. (2015) Multimodal chemosensory circuits controlling male courtship in Drosophila. Neuron 87:1036–1049",
    "kohatsu2011": "Kohatsu S., Koganezawa M., Yamamoto D. (2011) Female contact activates male-specific interneurons that trigger stereotypic courtship behavior in Drosophila. Neuron 69:498–508",
    "inagaki2014": "Inagaki H.K. et al. (2014) Optogenetic control of Drosophila using a red-shifted channelrhodopsin reveals experience-dependent influences on courtship. Nat Methods 11:325–332",
    "vonphilipsborn2011": "von Philipsborn A.C. et al. (2011) Neuronal control of Drosophila courtship song. Neuron 69:509–522",
    "zhang2016": "Zhang S.X., Rogulja D., Crickmore M.A. (2016) Dopaminergic circuitry underlying mating drive. Neuron 91:168–181",
    "ribeiro2018": "Ribeiro I.M.A. et al. (2018) Visual projection neurons mediating directed courtship in Drosophila. Cell 174:607–621",
    "seeholzer2018": "Seeholzer L.F. et al. (2018) Evolution of a central neural circuit underlies Drosophila mate preferences. Nature 559:564–569",
    "laturney2016": "Laturney M., Billeter J.-C. (2016) Drosophila melanogaster females restore their attractiveness after mating by removing male anti-aphrodisiac pheromones. Nat Commun 7:12322",
    "krstic2009": "Krstic D., Boll W., Noll M. (2009) Sensory integration regulating male courtship behavior in Drosophila. PLoS One 4:e4457",
}


def sc(**kw):
    return {"target": "virgin", **kw}


BEHAVIOR = [
    dict(id="m_virgin", split="train", scenario=sc(), court=[0.6, 0.95], song=[0.4, 0.95],
         title_ru="Самец + девственная самка D. melanogaster",
         evidence_ru="Зрелые самцы активно ухаживают за девственными самками своего вида и поют.",
         source=["thistle2012", "kohatsu2011"]),
    dict(id="m_mated", split="train", scenario=sc(target="mated"), court=[0.15, 0.55],
         title_ru="Самец + недавно спарившаяся самка",
         evidence_ru="После спаривания на самке остаются феромоны самца (cVA, 7-трикозен), и другие самцы ухаживают за ней заметно меньше.",
         source=["laturney2016", "kurtovic2007"]),
    dict(id="m_male", split="train", scenario=sc(target="male"), court=[0.0, 0.15],
         title_ru="Самец + другой самец",
         evidence_ru="Самцы дикого типа почти не ухаживают за самцами: их отталкивают 7-трикозен и cVA.",
         source=["kurtovic2007", "thistle2012", "wang2011"]),
    dict(id="m_sim", split="test", scenario=sc(target="sim"), court=[0.1, 0.6],
         title_ru="Самец + самка D. simulans",
         evidence_ru="У самок D. simulans нет феромона 7,11-HD, который возбуждает ухаживание самцов D. melanogaster.",
         source=["seeholzer2018"]),
    dict(id="m_dark", split="test", scenario=sc(dark=True), court=[0.2, 0.75],
         title_ru="Самец + девственница в темноте",
         evidence_ru="Без зрения ухаживание слабее, но не исчезает: остаются вкус и запах.",
         source=["krstic2009"]),
    dict(id="m_or67d_male", split="train", scenario=sc(target="male", or67d_mutant=True), court=[0.15, 0.7],
         title_ru="Мутант Or67d (не чует cVA) + самец",
         evidence_ru="Самцы без рецептора Or67d ухаживают за другими самцами.",
         source=["kurtovic2007"]),
    dict(id="m_gr32a_male", split="test", scenario=sc(target="male", gr32a_mutant=True), court=[0.15, 0.7],
         title_ru="Мутант Gr32a + самец",
         evidence_ru="Без вкусового рецептора Gr32a самцы хуже распознают 7-трикозен и ухаживают за самцами.",
         source=["miyamoto2008", "wang2011"]),
    dict(id="m_ppk23_virgin", split="train", scenario=sc(ppk23_mutant=True), court=[0.2, 0.6],
         title_ru="Мутант ppk23 + девственница",
         evidence_ru="Без канала ppk23 самцы хуже чувствуют феромон самки и ухаживают реже и позже.",
         source=["thistle2012", "lu2012", "toda2012"]),
    dict(id="m_alone", split="train", scenario=sc(target="none"), court=[0.0, 0.1], song=[0.0, 0.1],
         title_ru="Самец один, без цели",
         evidence_ru="Без самки самец не ухаживает и не поёт.",
         source=["kohatsu2011"]),
    dict(id="m_p1_act", split="train", scenario=sc(target="none", activate=["P1"]), court=[0.5, 1.0], song=[0.5, 1.0],
         title_ru="Активация P1 у одинокого самца",
         evidence_ru="Активация нейронов P1 запускает ухаживание и песню даже без самки.",
         source=["kohatsu2011", "inagaki2014"]),
    dict(id="m_pip10_act", split="train", scenario=sc(target="none", activate=["pIP10"]), song=[0.5, 1.0],
         title_ru="Активация pIP10 у одинокого самца",
         evidence_ru="Активация нисходящих нейронов pIP10 вызывает песню крыльями.",
         source=["vonphilipsborn2011"]),
    dict(id="m_sated", split="train", scenario=sc(satiety=1.0), court=[0.0, 0.35],
         title_ru="Пресыщенный самец (несколько спариваний подряд) + девственница",
         evidence_ru="После серии спариваний мотивация падает: дофаминовый сигнал на P1 (рецептор DopR2) ослабевает.",
         source=["zhang2016"]),
]

FEM_ONLY = dict(target="none", hd=1.0)
MAL_ONLY = dict(target="none", t7=1.0)
NONE = dict(target="none")
PHYS = [
    dict(id="P1_female", group="P1", a=sc(), b=NONE, rel=">", margin=0.15, source=["kohatsu2011"],
         text_ru="P1 возбуждаются при контакте с самкой"),
    dict(id="P1_vs_male", group="P1", a=sc(), b=sc(target="male"), rel=">", margin=0.15, source=["clowney2015", "kallman2015"],
         text_ru="P1 сильнее отвечают на самку, чем на самца"),
    dict(id="PPN1_F", group="PPN1", a=FEM_ONLY, b=NONE, rel=">", margin=0.1, source=["kallman2015"],
         text_ru="PPN1 отвечают на феромон самки (F-клетки)"),
    dict(id="vAB3_F", group="vAB3", a=FEM_ONLY, b=MAL_ONLY, rel=">", margin=0.05, source=["clowney2015"],
         text_ru="vAB3 отвечают на феромоны самки, а не самца"),
    dict(id="mAL_M", group="mAL", a=MAL_ONLY, b=NONE, rel=">", margin=0.05, source=["kallman2015", "clowney2015"],
         text_ru="mAL возбуждаются феромоном самца"),
    dict(id="mAL_F", group="mAL", a=FEM_ONLY, b=NONE, rel=">", margin=0.03, source=["kallman2015"],
         text_ru="mAL возбуждаются и феромоном самки (торможение «на всякий случай»)"),
    dict(id="pIP10_P1", group="pIP10", a=dict(target="none", activate=["P1"]), b=NONE, rel=">", margin=0.2,
         source=["vonphilipsborn2011"], text_ru="P1 управляют командным нейроном песни pIP10"),
    dict(id="song_pIP10", group="song", a=dict(target="none", activate=["pIP10"]), b=NONE, rel=">", margin=0.1,
         source=["vonphilipsborn2011"], text_ru="pIP10 включают генератор песни в грудных ганглиях"),
    dict(id="LC10a_vis", group="LC10a", a=sc(), b=sc(dark=True), rel=">", margin=0.1, source=["ribeiro2018"],
         text_ru="LC10a отвечают на движущуюся цель"),
    dict(id="PN_cVA", group="PN_cVA", a=dict(target="none", cva=1.0), b=NONE, rel=">", margin=0.1, source=["kurtovic2007"],
         text_ru="Проекционные нейроны DA1 отвечают на cVA"),
]


def main() -> None:
    for b in BEHAVIOR:
        for s in b["source"]:
            assert s in SRC, s
    out = {"description_ru": "Обучающие данные: опубликованные эксперименты об ухаживании самца D. melanogaster.",
           "sources": SRC, "behavior": BEHAVIOR, "physiology": PHYS}
    path = LITERATURE / "male_experiments.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    n_train = sum(b["split"] == "train" for b in BEHAVIOR)
    print(f"Записано {path}: {len(BEHAVIOR)} опытов ({n_train} обучение, {len(BEHAVIOR) - n_train} тест), "
          f"{len(PHYS)} физиологических фактов.")


if __name__ == "__main__":
    main()
