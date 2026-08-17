'''this .py holds the interface translation catalogue and the language handling
for English, Italian and French.
'''

from __future__ import annotations

import streamlit as st

#Supported languages
LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"endonym": "English",  "flagless_code": "EN", "name_in_english": "English"},
    "it": {"endonym": "Italiano", "flagless_code": "IT", "name_in_english": "Italian"},
    "fr": {"endonym": "Français", "flagless_code": "FR", "name_in_english": "French"},
}

DEFAULT_LANGUAGE = "en"
LANGUAGE_ORDER = ("en", "it", "fr")


def language_options() -> list[str]:
    return list(LANGUAGE_ORDER)




def language_label(code: str) -> str:
    meta = LANGUAGES.get(code, LANGUAGES[DEFAULT_LANGUAGE])
    return f"{meta['flagless_code']}  {meta['endonym']}"


def default_language() -> str:
    try:
        locale = (st.context.locale or "").lower()
    except Exception:
        return DEFAULT_LANGUAGE
    for code in LANGUAGE_ORDER:
        if locale.startswith(code):
            return code
    return DEFAULT_LANGUAGE


#Catalogue

STRINGS: dict[str, dict[str, str]] = {
    #Masthead 
    #product name is not translated
    "app.title": {
        "en": "Cyber Tutor",
        "it": "Cyber Tutor",
        "fr": "Cyber Tutor",
    },
    "app.subtitle": {
        "en": "Answers drawn only from your Weeks 1-5 course material, each one "
              "carrying a confidence band and a check on the foundations it builds on.",
        "it": "Risposte tratte esclusivamente dal materiale del corso delle settimane "
              "1-5, ciascuna con un livello di affidabilità e una verifica delle basi "
              "su cui si fonda.",
        "fr": "Des réponses tirées uniquement du matériel de cours des semaines 1 à 5, "
              "chacune accompagnée d'un niveau de confiance et d'une vérification des "
              "notions dont elle dépend.",
    },
    "app.scope": {
        "en": "Weeks 1-5 · Network Security",
        "it": "Settimane 1-5 · Sicurezza delle Reti",
        "fr": "Semaines 1 à 5 · Sécurité des Réseaux",
    },

    #--- Welcome panel
    "hero.lead": {
        "en": "Ask anything about Weeks 1-5 of the module. Every answer is built "
              "from your own course material rather than from the open internet.",
        "it": "Fai qualsiasi domanda sulle settimane 1-5 del modulo. Ogni risposta è "
              "costruita a partire dal materiale del tuo corso, non da internet.",
        "fr": "Posez n'importe quelle question sur les semaines 1 à 5 du module. Chaque "
              "réponse est construite à partir de votre matériel de cours, et non "
              "d'internet.",
    },
    "hero.f1.title": {
        "en": "Grounded in your module",
        "it": "Ancorato al tuo modulo",
        "fr": "Ancré dans votre module",
    },
    "hero.f1.body": {
        "en": "Answers are retrieved from the Weeks 1-5 lectures, knowledge checks and "
              "past papers, and cite the week they came from.",
        "it": "Le risposte provengono dalle lezioni, dai quiz e dagli esami passati "
              "delle settimane 1-5, e citano la settimana da cui derivano.",
        "fr": "Les réponses proviennent des cours, des quiz et des annales des semaines "
              "1 à 5, et citent la semaine dont elles sont issues.",
    },
    "hero.f2.title": {
        "en": "Confidence you can see",
        "it": "Affidabilità sempre visibile",
        "fr": "Une confiance visible",
    },
    "hero.f2.body": {
        "en": "Each answer carries a High, Medium or Low band, so you know when to "
              "check it against KEATS before relying on it.",
        "it": "Ogni risposta riporta un livello Alto, Medio o Basso, così sai quando "
              "verificarla su KEATS prima di fidarti.",
        "fr": "Chaque réponse porte un niveau Élevé, Moyen ou Faible, pour savoir quand "
              "la vérifier sur KEATS avant de vous y fier.",
    },
    "hero.f3.title": {
        "en": "Foundations checked first",
        "it": "Prima le basi",
        "fr": "Les bases d'abord",
    },
    "hero.f3.body": {
        "en": "Ask something advanced and the tutor tests the concept underneath it "
              "before explaining, rather than assuming you have it.",
        "it": "Se fai una domanda avanzata, il tutor verifica il concetto che ne sta "
              "alla base prima di spiegare, invece di darlo per scontato.",
        "fr": "Pour une question avancée, le tuteur teste la notion sous-jacente avant "
              "d'expliquer, au lieu de la supposer acquise.",
    },
    "hero.try": {
        "en": "Try one of these",
        "it": "Prova una di queste",
        "fr": "Essayez l'une de ces questions",
    },

    #Chat
    "chat.placeholder": {
        "en": "Ask a question, or a follow-up…",
        "it": "Fai una domanda, o un approfondimento…",
        "fr": "Posez une question, ou une question de suivi…",
    },
    "chat.retrieving": {
        "en": "Retrieving course material…",
        "it": "Recupero del materiale del corso…",
        "fr": "Récupération du matériel de cours…",
    },
    "chat.translating": {
        "en": "Preparing your question for search…",
        "it": "Preparazione della domanda per la ricerca…",
        "fr": "Préparation de votre question pour la recherche…",
    },

    #Confidence bands
    "band.confidence": {
        "en": "confidence", "it": "affidabilità", "fr": "confiance",
    },
    "band.High": {"en": "High", "it": "Alta", "fr": "Élevée"},
    "band.Medium": {"en": "Medium", "it": "Media", "fr": "Moyenne"},
    "band.Low": {"en": "Low", "it": "Bassa", "fr": "Faible"},
    "band.High.text": {
        "en": "The answer is well supported by the retrieved course material.",
        "it": "La risposta è ben supportata dal materiale del corso recuperato.",
        "fr": "La réponse est bien étayée par le matériel de cours récupéré.",
    },
    "band.Medium.text": {
        "en": "The answer is grounded in the course material, but some details may go "
              "beyond the retrieved sources.",
        "it": "La risposta è fondata sul materiale del corso, ma alcuni dettagli "
              "potrebbero andare oltre le fonti recuperate.",
        "fr": "La réponse s'appuie sur le matériel de cours, mais certains détails "
              "peuvent dépasser les sources récupérées.",
    },
    "band.Low.text": {
        "en": "The knowledge base may not contain enough material on this topic. Check "
              "your KEATS materials or ask your lecturer before relying on this answer.",
        "it": "La base di conoscenza potrebbe non contenere materiale sufficiente su "
              "questo argomento. Controlla i materiali su KEATS o chiedi al docente "
              "prima di fare affidamento su questa risposta.",
        "fr": "La base de connaissances ne contient peut-être pas assez de matériel sur "
              "ce sujet. Consultez vos supports KEATS ou votre enseignant avant de vous "
              "fier à cette réponse.",
    },

    #Answer detail dialogue
    "details.title": {
        "en": "Answer details", "it": "Dettagli della risposta",
        "fr": "Détails de la réponse",
    },
    "details.help": {
        "en": "Show answer details", "it": "Mostra i dettagli della risposta",
        "fr": "Afficher les détails de la réponse",
    },
    "details.you_asked": {
        "en": "You asked", "it": "Hai chiesto", "fr": "Vous avez demandé",
    },
    "details.final": {
        "en": "Final confidence", "it": "Affidabilità finale",
        "fr": "Confiance finale",
    },
    "details.signal1": {
        "en": "Signal 1 (retrieval)", "it": "Segnale 1 (recupero)",
        "fr": "Signal 1 (récupération)",
    },
    "details.signal1.note": {
        "en": "mean cosine distance {d}", "it": "distanza coseno media {d}",
        "fr": "distance cosinus moyenne {d}",
    },
    "details.signal2": {
        "en": "Signal 2 (self-verification)", "it": "Segnale 2 (auto-verifica)",
        "fr": "Signal 2 (auto-vérification)",
    },
    "details.latency": {
        "en": "Response time", "it": "Tempo di risposta", "fr": "Temps de réponse",
    },
    "details.sources_n": {
        "en": "Sources retrieved", "it": "Fonti recuperate",
        "fr": "Sources récupérées",
    },
    "details.simplified": {
        "en": "Simplified after an incomplete prerequisite check.",
        "it": "Semplificata a seguito di una verifica dei prerequisiti incompleta.",
        "fr": "Simplifiée après une vérification des prérequis incomplète.",
    },
    "details.followup": {
        "en": "Follow-up detected: retrieval was anchored to the earlier question.",
        "it": "Approfondimento rilevato: il recupero è stato ancorato alla domanda "
              "precedente.",
        "fr": "Question de suivi détectée : la récupération a été rattachée à la "
              "question précédente.",
    },
    "details.translated": {
        "en": "Searched using the English rendering: \"{q}\"",
        "it": "Ricerca effettuata con la resa inglese: \"{q}\"",
        "fr": "Recherche effectuée avec la formulation anglaise : \"{q}\"",
    },

    "verify.3": {
        "en": "3 - well supported", "it": "3 - ben supportata",
        "fr": "3 - bien étayée",
    },
    "verify.2": {
        "en": "2 - partially supported", "it": "2 - parzialmente supportata",
        "fr": "2 - partiellement étayée",
    },
    "verify.1": {
        "en": "1 - poorly supported", "it": "1 - scarsamente supportata",
        "fr": "1 - faiblement étayée",
    },

    #Soources
    "sources.title": {
        "en": "Sources ({n})", "it": "Fonti ({n})", "fr": "Sources ({n})",
    },
    "sources.week": {"en": "Week {n}", "it": "Sett. {n}", "fr": "Sem. {n}"},
    "sources.relevance": {
        "en": "relevance", "it": "pertinenza", "fr": "pertinence",
    },
    "sources.distance": {
        "en": "distance", "it": "distanza", "fr": "distance",
    },
    "sources.excerpt": {
        "en": "Show the retrieved passage",
        "it": "Mostra il passaggio recuperato",
        "fr": "Afficher le passage récupéré",
    },
    "sources.note": {
        "en": "These are the exact passages the answer was written from. If a claim in "
              "the answer is not in one of them, treat it with caution.",
        "it": "Questi sono esattamente i passaggi da cui è stata scritta la risposta. Se "
              "un'affermazione della risposta non compare in nessuno di essi, trattala "
              "con cautela.",
        "fr": "Ce sont exactement les passages à partir desquels la réponse a été "
              "rédigée. Si une affirmation de la réponse n'y figure pas, considérez-la "
              "avec prudence.",
    },

    #Prerequisite probe
    "mcq.eyebrow": {
        "en": "Prerequisite checkpoint", "it": "Verifica dei prerequisiti",
        "fr": "Point de contrôle des prérequis",
    },
    "mcq.intro": {
        "en": "That question builds on **{topic}**. Before I answer, let's check that "
              "foundation with {n} quick questions.",
        "it": "Questa domanda si basa su **{topic}**. Prima di rispondere, verifichiamo "
              "quelle basi con {n} domande rapide.",
        "fr": "Cette question repose sur **{topic}**. Avant de répondre, vérifions ces "
              "bases avec {n} questions rapides.",
    },
    "mcq.qcount": {
        "en": "Question {i} of {n}", "it": "Domanda {i} di {n}",
        "fr": "Question {i} sur {n}",
    },
    "mcq.submit": {
        "en": "Submit answers", "it": "Invia le risposte",
        "fr": "Envoyer les réponses",
    },

    "prereq.passed": {
        "en": "Prerequisite check passed ({score}/{total}). Here is the full explanation.",
        "it": "Verifica dei prerequisiti superata ({score}/{total}). Ecco la spiegazione "
              "completa.",
        "fr": "Vérification des prérequis réussie ({score}/{total}). Voici l'explication "
              "complète.",
    },
    "prereq.failed": {
        "en": "Prerequisite check: {score}/{total}. Here is a simplified explanation. "
              "Review **{topic}** on KEATS before going further.",
        "it": "Verifica dei prerequisiti: {score}/{total}. Ecco una spiegazione "
              "semplificata. Ripassa **{topic}** su KEATS prima di proseguire.",
        "fr": "Vérification des prérequis : {score}/{total}. Voici une explication "
              "simplifiée. Revoyez **{topic}** sur KEATS avant d'aller plus loin.",
    },
    "prereq.review_one": {
        "en": "Review your 1 incorrect answer",
        "it": "Rivedi la tua risposta errata",
        "fr": "Revoir votre réponse incorrecte",
    },
    "prereq.review_many": {
        "en": "Review your {n} incorrect answers",
        "it": "Rivedi le tue {n} risposte errate",
        "fr": "Revoir vos {n} réponses incorrectes",
    },
    "prereq.you_chose": {
        "en": "You chose", "it": "Hai scelto", "fr": "Vous avez choisi",
    },
    "prereq.correct": {
        "en": "Correct answer", "it": "Risposta corretta", "fr": "Bonne réponse",
    },
    "prereq.no_answer": {
        "en": "no answer given", "it": "nessuna risposta data",
        "fr": "aucune réponse donnée",
    },
    "prereq.state_passed": {
        "en": "passed", "it": "superato", "fr": "réussi",
    },
    "prereq.state_review": {
        "en": "needs review", "it": "da ripassare", "fr": "à revoir",
    },

    #Follow-up suggestions
    "followups.title": {
        "en": "Continue with", "it": "Continua con", "fr": "Poursuivre avec",
    },
    "followups.simpler": {
        "en": "Explain that more simply",
        "it": "Spiegalo in modo più semplice",
        "fr": "Explique cela plus simplement",
    },
    "followups.example": {
        "en": "Give me a worked example",
        "it": "Fammi un esempio pratico",
        "fr": "Donne-moi un exemple concret",
    },
    "followups.detect": {
        "en": "How is {topic} detected or prevented?",
        "it": "Come si rileva o si previene {topic}?",
        "fr": "Comment détecter ou prévenir {topic} ?",
    },
    "followups.relate": {
        "en": "How does this relate to {topic}?",
        "it": "Che rapporto ha con {topic}?",
        "fr": "Quel est le rapport avec {topic} ?",
    },
    "followups.exam": {
        "en": "How might this be examined?",
        "it": "Come potrebbe essere chiesto all'esame?",
        "fr": "Comment cela pourrait-il tomber à l'examen ?",
    },
    "followups.test_me": {
        "en": "Test me on {topic}",
        "it": "Mettimi alla prova su {topic}",
        "fr": "Teste-moi sur {topic}",
    },

    #Session progress
    "progress.title": {
        "en": "Your session", "it": "La tua sessione", "fr": "Votre session",
    },
    "progress.questions": {
        "en": "Questions asked", "it": "Domande poste", "fr": "Questions posées",
    },
    "progress.weeks": {
        "en": "Weeks covered", "it": "Settimane coperte", "fr": "Semaines couvertes",
    },
    "progress.topics": {
        "en": "Topics touched", "it": "Argomenti toccati", "fr": "Sujets abordés",
    },
    "progress.latency": {
        "en": "Average response", "it": "Risposta media", "fr": "Réponse moyenne",
    },
    "progress.mix": {
        "en": "Confidence mix", "it": "Distribuzione affidabilità",
        "fr": "Répartition de la confiance",
    },
    "progress.empty": {
        "en": "Ask your first question and your session summary appears here.",
        "it": "Fai la tua prima domanda e qui comparirà il riepilogo della sessione.",
        "fr": "Posez votre première question et le résumé de votre session apparaîtra ici.",
    },

    #Sidebar
    "sidebar.language": {
        "en": "Language", "it": "Lingua", "fr": "Langue",
    },
    "sidebar.language_help": {
        "en": "Changes the interface and the language answers are written in. The course "
              "material itself is in English and is searched in English.",
        "it": "Cambia l'interfaccia e la lingua in cui sono scritte le risposte. Il "
              "materiale del corso è in inglese e viene cercato in inglese.",
        "fr": "Change l'interface et la langue des réponses. Le matériel de cours est en "
              "anglais et la recherche s'y effectue en anglais.",
    },
    "sidebar.new": {
        "en": "New conversation", "it": "Nuova conversazione",
        "fr": "Nouvelle conversation",
    },
    "sidebar.previous": {
        "en": "Previous conversations", "it": "Conversazioni precedenti",
        "fr": "Conversations précédentes",
    },
    "sidebar.prereqs": {
        "en": "Prerequisites checked", "it": "Prerequisiti verificati",
        "fr": "Prérequis vérifiés",
    },
    "sidebar.key": {
        "en": "Confidence key", "it": "Legenda affidabilità",
        "fr": "Légende de la confiance",
    },
    "sidebar.grounded": {
        "en": "Grounded in Weeks 1-5 of the module. Answers come only from course "
              "material, and each one carries a confidence band.",
        "it": "Basato sulle settimane 1-5 del modulo. Le risposte provengono solo dal "
              "materiale del corso e ciascuna riporta un livello di affidabilità.",
        "fr": "Fondé sur les semaines 1 à 5 du module. Les réponses proviennent "
              "uniquement du matériel de cours et portent chacune un niveau de confiance.",
    },
    "sidebar.dark_mode": {
        "en": "Dark mode", "it": "Modalità scura", "fr": "Mode sombre",
    },
    "sidebar.light_mode": {
        "en": "Light mode", "it": "Modalità chiara", "fr": "Mode clair",
    },
    "sidebar.export": {
        "en": "Download this conversation", "it": "Scarica questa conversazione",
        "fr": "Télécharger cette conversation",
    },
    "sidebar.export_help": {
        "en": "Saves the thread as a Markdown file, with the confidence band and the "
              "sources for every answer, so it can be kept as revision notes.",
        "it": "Salva la conversazione come file Markdown, con il livello di affidabilità "
              "e le fonti di ogni risposta, per conservarla come appunti di ripasso.",
        "fr": "Enregistre la conversation en Markdown, avec le niveau de confiance et les "
              "sources de chaque réponse, pour la conserver comme fiche de révision.",
    },

    #Guard replies
    "guard.non_question": {
        "en": "I don't see a specific question in \"{msg}\". Ask me something about "
              "Weeks 1-5 of the module - for example, \"What is ARP spoofing?\"",
        "it": "Non vedo una domanda precisa in \"{msg}\". Chiedimi qualcosa sulle "
              "settimane 1-5 del modulo - per esempio, \"Che cos'è l'ARP spoofing?\"",
        "fr": "Je ne vois pas de question précise dans \"{msg}\". Posez-moi une question "
              "sur les semaines 1 à 5 du module - par exemple, \"Qu'est-ce que "
              "l'usurpation ARP ?\"",
    },
    "guard.bare": {
        "en": "\"{msg}\" on its own doesn't give me enough to work with. Could you ask a "
              "fuller question - for example, \"How does ARP spoofing work?\" If you're "
              "following up on my last answer, try \"tell me more\" or name the part "
              "you'd like unpacked.",
        "it": "\"{msg}\" da solo non mi dà abbastanza su cui lavorare. Puoi fare una "
              "domanda più completa - per esempio, \"Come funziona l'ARP spoofing?\" Se "
              "stai approfondendo la mia ultima risposta, prova con \"dimmi di più\" o "
              "indica la parte che vuoi chiarire.",
        "fr": "\"{msg}\" seul ne me donne pas de quoi travailler. Pourriez-vous poser une "
              "question plus complète - par exemple, \"Comment fonctionne l'usurpation "
              "ARP ?\" Si vous revenez sur ma dernière réponse, essayez \"dis-m'en "
              "plus\" ou précisez le point à développer.",
    },

    #Export
    "export.heading": {
        "en": "Cyber Tutor - conversation",
        "it": "Cyber Tutor - conversazione",
        "fr": "Cyber Tutor - conversation",
    },
    "export.exported_on": {
        "en": "Exported", "it": "Esportato il", "fr": "Exporté le",
    },
    "export.you": {"en": "You", "it": "Tu", "fr": "Vous"},
    "export.tutor": {"en": "Tutor", "it": "Tutor", "fr": "Tuteur"},
    "export.disclaimer": {
        "en": "Generated by a retrieval-augmented tutor from Weeks 1-5 course material. "
              "Check anything marked Medium or Low against KEATS.",
        "it": "Generato da un tutor ad aumento per recupero a partire dal materiale delle "
              "settimane 1-5. Verifica su KEATS tutto ciò che è segnato Media o Bassa.",
        "fr": "Généré par un tuteur à génération augmentée par récupération à partir du "
              "matériel des semaines 1 à 5. Vérifiez sur KEATS tout ce qui est marqué "
              "Moyenne ou Faible.",
    },
    #Quiz
    "nav.tutor": {"en": "Tutor", "it": "Tutor", "fr": "Tuteur"},
    "nav.quiz": {"en": "Quiz", "it": "Quiz", "fr": "Quiz"},
    "nav.section": {"en": "Mode", "it": "Modalità", "fr": "Mode"},

    "quiz.title": {
        "en": "Test yourself",
        "it": "Mettiti alla prova",
        "fr": "Testez-vous",
    },
    "quiz.intro": {
        "en": "Build a quiz from the Weeks 1-5 course material. Choose how "
              "hard, how long, and what to cover.",
        "it": "Crea un quiz a partire dal materiale delle settimane 1-5. "
              "Scegli difficoltà, lunghezza e argomenti.",
        "fr": "Composez un questionnaire à partir du matériel des semaines 1 "
              "à 5. Choisissez la difficulté, la longueur et les sujets.",
    },
    "quiz.difficulty": {
        "en": "Difficulty", "it": "Difficoltà", "fr": "Difficulté",
    },
    "quiz.difficulty.easy": {"en": "Easy", "it": "Facile", "fr": "Facile"},
    "quiz.difficulty.medium": {"en": "Medium", "it": "Media", "fr": "Moyenne"},
    "quiz.difficulty.hard": {"en": "Hard", "it": "Difficile", "fr": "Difficile"},
    "quiz.difficulty.easy_help": {
        "en": "Recall and recognition, answerable from a single definition.",
        "it": "Richiamo e riconoscimento, si risponde con una sola definizione.",
        "fr": "Rappel et reconnaissance, à partir d'une seule définition.",
    },
    "quiz.difficulty.medium_help": {
        "en": "Application and comparison, connecting two ideas.",
        "it": "Applicazione e confronto, collegando due concetti.",
        "fr": "Application et comparaison, en reliant deux notions.",
    },
    "quiz.difficulty.hard_help": {
        "en": "Analysis and reasoning about why a mechanism behaves as it does.",
        "it": "Analisi e ragionamento sul perché un meccanismo si comporta così.",
        "fr": "Analyse et raisonnement sur le comportement d'un mécanisme.",
    },
    "quiz.count": {
        "en": "Number of questions", "it": "Numero di domande",
        "fr": "Nombre de questions",
    },
    "quiz.count_help": {
        "en": "Between 1 and 20.",
        "it": "Tra 1 e 20.",
        "fr": "Entre 1 et 20.",
    },
    "quiz.topics": {"en": "Topics", "it": "Argomenti", "fr": "Sujets"},
    "quiz.topics_help": {
        "en": "Leave empty to draw from every topic.",
        "it": "Lascia vuoto per attingere a tutti gli argomenti.",
        "fr": "Laissez vide pour puiser dans tous les sujets.",
    },
    "quiz.topics_all": {
        "en": "All topics", "it": "Tutti gli argomenti", "fr": "Tous les sujets",
    },
    "quiz.mode": {"en": "Mode", "it": "Modalità", "fr": "Mode"},
    "quiz.mode.practice": {
        "en": "Practice", "it": "Esercitazione", "fr": "Entraînement",
    },
    "quiz.mode.exam": {"en": "Exam", "it": "Esame", "fr": "Examen"},
    "quiz.mode.practice_help": {
        "en": "No timer. You may choose to see each answer as you go.",
        "it": "Nessun timer. Puoi scegliere di vedere ogni risposta subito.",
        "fr": "Sans chronomètre. Vous pouvez voir chaque réponse au fur et à mesure.",
    },
    "quiz.mode.exam_help": {
        "en": "Timed at one minute per question. Answers are shown only at the end.",
        "it": "Un minuto per domanda. Le risposte si vedono solo alla fine.",
        "fr": "Une minute par question. Les réponses ne sont visibles qu'à la fin.",
    },
    "quiz.reveal": {
        "en": "Show the answer after each question",
        "it": "Mostra la risposta dopo ogni domanda",
        "fr": "Afficher la réponse après chaque question",
    },
    "quiz.reveal_help": {
        "en": "Available in practice mode only. Being told why an answer was "
              "wrong is what turns a test into revision.",
        "it": "Disponibile solo in esercitazione. Sapere perché una risposta "
              "era sbagliata è ciò che trasforma un test in ripasso.",
        "fr": "Disponible uniquement en entraînement. Savoir pourquoi une "
              "réponse était fausse transforme le test en révision.",
    },
    "quiz.reveal_exam_note": {
        "en": "Exam mode withholds answers until the end.",
        "it": "In modalità esame le risposte compaiono solo alla fine.",
        "fr": "En mode examen, les réponses n'apparaissent qu'à la fin.",
    },
    "quiz.start": {
        "en": "Start quiz", "it": "Inizia il quiz", "fr": "Commencer",
    },
    "quiz.generating": {
        "en": "Writing your questions from the course material...",
        "it": "Sto scrivendo le domande dal materiale del corso...",
        "fr": "Rédaction de vos questions à partir du matériel de cours...",
    },
    "quiz.summary_line": {
        "en": "{count} questions - {difficulty} - {mode}",
        "it": "{count} domande - {difficulty} - {mode}",
        "fr": "{count} questions - {difficulty} - {mode}",
    },
    "quiz.progress": {
        "en": "Question {i} of {n}", "it": "Domanda {i} di {n}",
        "fr": "Question {i} sur {n}",
    },
    "quiz.time_left": {
        "en": "Time remaining", "it": "Tempo rimanente", "fr": "Temps restant",
    },
    "quiz.time_up": {
        "en": "Time is up. Your answers so far have been submitted.",
        "it": "Tempo scaduto. Le risposte date finora sono state inviate.",
        "fr": "Le temps est écoulé. Vos réponses ont été soumises.",
    },
    "quiz.check": {"en": "Check answer", "it": "Verifica", "fr": "Vérifier"},
    "quiz.next": {"en": "Next question", "it": "Domanda successiva",
                  "fr": "Question suivante"},
    "quiz.finish": {"en": "Finish and see results", "it": "Termina e vedi i risultati",
                    "fr": "Terminer et voir les résultats"},
    "quiz.previous": {"en": "Back", "it": "Indietro", "fr": "Retour"},
    "quiz.abandon": {
        "en": "Abandon quiz", "it": "Abbandona il quiz",
        "fr": "Abandonner",
    },
    "quiz.pick_one": {
        "en": "Choose an option before continuing.",
        "it": "Scegli un'opzione prima di continuare.",
        "fr": "Choisissez une option avant de continuer.",
    },
    "quiz.unanswered": {
        "en": "{n} unanswered", "it": "{n} senza risposta",
        "fr": "{n} sans réponse",
    },
    "quiz.was_correct": {
        "en": "Correct", "it": "Corretto", "fr": "Correct",
    },
    "quiz.was_incorrect": {
        "en": "Not quite", "it": "Non proprio", "fr": "Pas tout à fait",
    },
    "quiz.your_answer": {
        "en": "You chose", "it": "Hai scelto", "fr": "Vous avez choisi",
    },
    "quiz.correct_answer": {
        "en": "Correct answer", "it": "Risposta corretta", "fr": "Bonne réponse",
    },
    "quiz.no_answer": {
        "en": "not answered", "it": "senza risposta", "fr": "sans réponse",
    },
    "quiz.from_week": {
        "en": "From Week {n}", "it": "Dalla settimana {n}",
        "fr": "Semaine {n}",
    },
    "quiz.results": {"en": "Your result", "it": "Il tuo risultato",
                     "fr": "Votre résultat"},
    "quiz.score_line": {
        "en": "{score} out of {total} correct",
        "it": "{score} risposte corrette su {total}",
        "fr": "{score} bonnes réponses sur {total}",
    },
    "quiz.review": {
        "en": "Review every question", "it": "Rivedi tutte le domande",
        "fr": "Revoir toutes les questions",
    },
    "quiz.retry": {
        "en": "New quiz", "it": "Nuovo quiz", "fr": "Nouveau questionnaire",
    },
    "quiz.ask_tutor": {
        "en": "Ask the tutor about this", "it": "Chiedi al tutor",
        "fr": "Interroger le tuteur",
    },
    "quiz.failed": {
        "en": "The questions could not be generated. This is usually a "
              "temporary API problem. Please try again.",
        "it": "Non è stato possibile generare le domande. Di solito è un "
              "problema temporaneo dell'API. Riprova.",
        "fr": "Les questions n'ont pas pu être générées. Il s'agit "
              "généralement d'un problème temporaire de l'API. Réessayez.",
    },
    "quiz.short": {
        "en": "Only {n} usable questions could be written for this "
              "combination. The quiz has been shortened.",
        "it": "Per questa combinazione sono state scritte solo {n} domande "
              "utilizzabili. Il quiz è stato accorciato.",
        "fr": "Seules {n} questions exploitables ont pu être rédigées pour "
              "cette combinaison. Le questionnaire a été raccourci.",
    },

    "quiz.err.rate_limit": {
        "en": "The free tier rate limit was reached. Wait about a minute, or "
              "ask for fewer questions or fewer topics, then try again.",
        "it": "È stato raggiunto il limite di richieste del piano gratuito. "
              "Attendi circa un minuto, oppure richiedi meno domande o meno "
              "argomenti, e riprova.",
        "fr": "La limite de requêtes de l'offre gratuite a été atteinte. "
              "Patientez environ une minute, ou demandez moins de questions ou "
              "moins de sujets, puis réessayez.",
    },
    "quiz.err.auth": {
        "en": "The API key was rejected. Check that GROQ_API_KEY is set "
              "correctly and has not expired.",
        "it": "La chiave API è stata rifiutata. Verifica che GROQ_API_KEY sia "
              "impostata correttamente e non sia scaduta.",
        "fr": "La clé API a été refusée. Verifiez que GROQ_API_KEY est "
              "correctement définie et n'a pas expiré.",
    },
    "quiz.err.model": {
        "en": "The configured model is unavailable. Check GROQ_MODEL in "
              "config.py against the models the provider currently offers.",
        "it": "Il modello configurato non è disponibile. Controlla GROQ_MODEL "
              "in config.py rispetto ai modelli attualmente offerti.",
        "fr": "Le modèle configuré est indisponible. Vérifiez GROQ_MODEL dans "
              "config.py par rapport aux modèles actuellement proposés.",
    },
    "quiz.err.too_long": {
        "en": "The request was too large for the model. Choose fewer topics "
              "and try again.",
        "it": "La richiesta era troppo grande per il modello. Scegli meno "
              "argomenti e riprova.",
        "fr": "La requête était trop volumineuse pour le modèle. Choisissez "
              "moins de sujets et réessayez.",
    },
    "quiz.err.no_context": {
        "en": "No course material could be retrieved for those topics. Check "
              "that the knowledge base has been built.",
        "it": "Non è stato possibile recuperare materiale per quegli "
              "argomenti. Verifica che la base di conoscenza sia stata creata.",
        "fr": "Aucun matériel de cours n'a pu être récupéré pour ces sujets. "
              "Vérifiez que la base de connaissances a été construite.",
    },
    "quiz.err.no_valid_questions": {
        "en": "The model replied, but none of the questions it wrote were "
              "usable. Try again, or choose a different difficulty.",
        "it": "Il modello ha risposto, ma nessuna delle domande scritte era "
              "utilizzabile. Riprova, o scegli una difficoltà diversa.",
        "fr": "Le modèle a répondu, mais aucune des questions rédigées n'était "
              "exploitable. Reessayez, ou choisissez une autre difficulté.",
    },
    "quiz.err.unknown": {
        "en": "The questions could not be generated. This is usually a "
              "temporary API problem. Please try again.",
        "it": "Non è stato possibile generare le domande. Di solito è un "
              "problema temporaneo dell'API. Riprova.",
        "fr": "Les questions n'ont pas pu être générées. Il s'agit "
              "généralement d'un problème temporaire de l'API. Reessayez.",
    },
    "quiz.generating_n": {
        "en": "Written {n} of {total} so far...",
        "it": "Scritte {n} su {total} finora...",
        "fr": "{n} sur {total} rédigées pour l'instant...",
    },

    "quiz.history": {
        "en": "Your quizzes", "it": "I tuoi quiz", "fr": "Vos questionnaires",
    },
    "quiz.history_empty": {
        "en": "No quizzes yet. Once you finish one, your score appears here.",
        "it": "Nessun quiz ancora. Quando ne completi uno, il punteggio compare qui.",
        "fr": "Aucun questionnaire pour l'instant. Votre score apparaîtra ici.",
    },
    "quiz.history_attempts": {
        "en": "Attempts", "it": "Tentativi", "fr": "Tentatives",
    },
    "quiz.history_average": {
        "en": "Average", "it": "Media", "fr": "Moyenne",
    },
    "quiz.history_best": {
        "en": "Best", "it": "Migliore", "fr": "Meilleur",
    },
    "quiz.history_clear": {
        "en": "Clear history", "it": "Cancella cronologia",
        "fr": "Effacer l'historique",
    },
    "quiz.history_count": {
        "en": "{n} questions", "it": "{n} domande", "fr": "{n} questions",
    },
    "quiz.history_more": {
        "en": "and {n} earlier", "it": "e altri {n} precedenti",
        "fr": "et {n} plus anciens",
    },

    "quiz.history_review": {
        "en": "Review", "it": "Rivedi", "fr": "Revoir",
    },
    "quiz.history_back": {
        "en": "Back to your quizzes", "it": "Torna ai tuoi quiz",
        "fr": "Retour à vos questionnaires",
    },
    "quiz.history_viewing": {
        "en": "Attempt of {when}", "it": "Tentativo del {when}",
        "fr": "Tentative du {when}",
    },
    "quiz.history_no_review": {
        "en": "This attempt was recorded before questions were kept, so only "
              "its score is available.",
        "it": "Questo tentativo è stato registrato prima che le domande "
              "venissero conservate, quindi è disponibile solo il punteggio.",
        "fr": "Cette tentative a été enregistrée avant que les questions ne "
              "soient conservees ; seul le score est disponible.",
    },

    # Quiz topic names, keyed by the identifiers in quiz.QUIZ_TOPICS
    "quiz.topic.foundations": {
        "en": "Security foundations", "it": "Fondamenti di sicurezza",
        "fr": "Fondements de la sécurité",
    },
    "quiz.topic.network_attacks": {
        "en": "Network attacks", "it": "Attacchi di rete",
        "fr": "Attaques réseau",
    },
    "quiz.topic.physical_layer": {
        "en": "Physical layer attacks", "it": "Attacchi al livello fisico",
        "fr": "Attaques de la couche physique",
    },
    "quiz.topic.interception": {
        "en": "Data interception", "it": "Intercettazione dei dati",
        "fr": "Interception de données",
    },
    "quiz.topic.arp": {
        "en": "ARP and ARP spoofing", "it": "ARP e ARP spoofing",
        "fr": "ARP et usurpation ARP",
    },
    "quiz.topic.dhcp": {
        "en": "DHCP attacks", "it": "Attacchi DHCP", "fr": "Attaques DHCP",
    },
    "quiz.topic.dos": {
        "en": "Denial of service and SYN flooding",
        "it": "Denial of service e SYN flooding",
        "fr": "Déni de service et inondation SYN",
    },
    "quiz.topic.bgp": {
        "en": "BGP and BGP hijacking", "it": "BGP e BGP hijacking",
        "fr": "BGP et détournement BGP",
    },
    "quiz.topic.dns": {
        "en": "DNS and cache poisoning", "it": "DNS e avvelenamento della cache",
        "fr": "DNS et empoisonnement du cache",
    },
    "quiz.topic.session_hijacking": {
        "en": "TCP session hijacking", "it": "Dirottamento di sessione TCP",
        "fr": "Détournement de session TCP",
    },
    "quiz.topic.firewall_types": {
        "en": "Firewall types and topologies", "it": "Tipi e topologie di firewall",
        "fr": "Types et topologies de pare-feu",
    },
    "quiz.topic.packet_filter": {
        "en": "Packet filter rules", "it": "Regole di filtraggio dei pacchetti",
        "fr": "Règles de filtrage de paquets",
    },
    "quiz.topic.stateful": {
        "en": "Stateful inspection", "it": "Ispezione stateful",
        "fr": "Inspection à état",
    },
}


#Prerequisite topic labels

TOPIC_LABELS: dict[str, dict[str, str]] = {
    "ARP protocol": {
        "en": "the ARP protocol",
        "it": "il protocollo ARP",
        "fr": "le protocole ARP",
    },
    "TCP handshake": {
        "en": "the TCP handshake",
        "it": "l'handshake TCP",
        "fr": "le handshake TCP",
    },
    "packet filter firewall": {
        "en": "packet filter firewalls",
        "it": "i firewall a filtraggio di pacchetti",
        "fr": "les pare-feu à filtrage de paquets",
    },
}


def topic_label(topic: str, lang: str) -> str:
    """Localised name for a prerequisite topic, falling back to the English key."""
    return TOPIC_LABELS.get(topic, {}).get(lang, topic)


#Starter questions

STARTER_QUESTIONS: dict[str, list[str]] = {
    "en": [
        "What is the CIA triad?",
        "How does ARP spoofing work?",
        "What is the difference between a stateful and a stateless firewall?",
    ],
    "it": [
        "Che cos'è la triade CIA?",
        "Come funziona l'ARP spoofing?",
        "Qual è la differenza tra un firewall stateful e uno stateless?",
    ],
    "fr": [
        "Qu'est-ce que la triade CIA ?",
        "Comment fonctionne l'usurpation ARP (ARP spoofing) ?",
        "Quelle est la différence entre un pare-feu à état et un pare-feu sans état ?",
    ],
}


#Lookup
def t(key: str, lang: str | None = None, **fmt) -> str:
    """
    Return the translated string for key, formatted with any keyword arguments.
    Falls back to English, and then to the key itself, so a missing translation
    degrades to a readable interface rather than a KeyError mid-conversation.
    """
    if lang is None:
        lang = current_language()
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get("en") or key
    if not fmt:
        return text
    try:
        return text.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return text


def current_language() -> str:
    """The language selected for this session.
    """
    return st.session_state.get("language") or DEFAULT_LANGUAGE


#Generation-side language control

def answer_language_instruction(lang: str) -> str:
    """Extra prompt clause instructing the model which language to answer in.
    """
    if lang == "en" or lang not in LANGUAGES:
        return ""

    language_name = LANGUAGES[lang]["name_in_english"]
    #Leading and trailing newlines are shaped to slot between the "Rules:"
    #block and "COURSE MATERIAL:" in build_prompt() without disturbing the
    #blank-line spacing of the prompt when the clause is empty.
    return (
        f"\nLANGUAGE:\n"
        f"- Write your entire answer in {language_name}. The student has asked "
        f"for {language_name} even though the course material below is in English.\n"
        f"- Keep protocol names, acronyms and standard technical terms in their "
        f"usual English form (ARP, TCP, SYN, DMZ, MAC, DNS), because those are "
        f"the terms used in the student's slides and examination paper.\n"
        f"- The final CONFIDENCE line must remain exactly as specified, in "
        f"English, and must not be translated.\n"
    )


#Language-aware conversational heuristics

FOLLOWUP_MARKERS: dict[str, tuple[str, ...]] = {
    "en": (
        "explain that", "explain it", "what about", "why is that", "why does that",
        "simpler", "more simply", "in simple terms", "elaborate", "expand on that",
        "more detail", "an example", "give me an example", "what do you mean",
        "and that", "how so", "tell me more", "go on", "clarify",
    ),
    "it": (
        "spiegalo", "spiega meglio", "spiegami meglio", "più semplice",
        "in modo semplice", "in parole semplici", "approfondisci", "elabora",
        "più dettagli", "un esempio", "fammi un esempio", "cosa intendi",
        "che cosa intendi", "dimmi di più", "vai avanti", "continua", "chiarisci",
        "e quello", "e questo", "come mai",
    ),
    "fr": (
        "explique cela", "explique-moi", "explique ça", "plus simplement",
        "en termes simples", "développe", "approfondis", "plus de détails",
        "un exemple", "donne-moi un exemple", "que veux-tu dire",
        "qu'est-ce que tu veux dire", "dis-m'en plus", "continue", "clarifie",
        "et ça", "et cela", "comment ça",
    ),
}

QUESTION_STARTERS: dict[str, tuple[str, ...]] = {
    "en": (
        "what", "whats", "why", "how", "when", "where", "which", "who", "whose",
        "is", "are", "was", "were", "can", "could", "does", "do", "did", "will",
        "would", "should", "explain", "define", "describe", "compare", "list",
        "name", "give", "tell", "state", "outline", "summarise", "summarize",
    ),
    "it": (
        "cosa", "cos'è", "cose", "che", "che cosa", "perché", "perche", "come",
        "quando", "dove", "quale", "quali", "qual", "chi", "è", "e'", "sono",
        "puoi", "potresti", "spiega", "spiegami", "definisci", "descrivi",
        "confronta", "elenca", "dimmi", "parlami", "riassumi", "in che",
    ),
    "fr": (
        "qu'est", "quest", "que", "quoi", "pourquoi", "comment", "quand", "où",
        "ou", "quel", "quelle", "quels", "quelles", "qui", "est", "sont", "peux",
        "peux-tu", "pourrais", "explique", "définis", "definis", "décris",
        "decris", "compare", "liste", "dis", "donne", "résume", "resume",
        "en quoi",
    ),
}

BARE_INTERROGATIVES: dict[str, tuple[str, ...]] = {
    "en": ("what", "whats", "why", "how", "when", "where", "which", "who", "whose"),
    "it": ("cosa", "perché", "perche", "come", "quando", "dove", "quale", "chi"),
    "fr": ("quoi", "pourquoi", "comment", "quand", "où", "ou", "quel", "quelle", "qui"),
}

#Module vocabulary.
MODULE_TERMS: tuple[str, ...] = (
    #Acronyms and protocol names, identical in all three languages
    "arp", "dhcp", "tcp", "udp", "dns", "ip", "mac", "osi", "syn", "cia",
    "dmz", "mitm", "vpn", "ssl", "tls", "icmp", "nat",
    #English
    "firewall", "spoof", "hijack", "poison", "attack", "security", "encrypt",
    "triad", "bastion", "smurf", "replay", "packet", "port", "protocol",
    "handshake", "flood", "gateway", "proxy", "stateful", "stateless",
    "confidentiality", "integrity", "availability", "authentication",
    "repudiation",
    #Italian
    "sicurezza", "attacco", "crittografia", "cifratura", "pacchetto", "porta",
    "protocollo", "autenticazione", "riservatezza", "integrità", "disponibilità",
    "avvelenamento", "usurpazione", "triade", "inondazione", "dirottamento",
    #French
    "sécurité", "securite", "attaque", "chiffrement", "paquet", "protocole",
    "authentification", "confidentialité", "confidentialite", "intégrité",
    "integrite", "disponibilité", "disponibilite", "empoisonnement",
    "usurpation", "triade", "pare-feu", "inondation", "détournement",
)


def followup_markers(lang: str) -> tuple[str, ...]:
    """Anaphoric markers for the active language plus English.

    English is always included: code-switching mid-thread is common among
    multilingual students, and a student typing "tell me more" while the
    interface is in Italian should still be understood as following up.
    """
    return FOLLOWUP_MARKERS["en"] + FOLLOWUP_MARKERS.get(lang, ())


def question_starters(lang: str) -> tuple[str, ...]:
    return QUESTION_STARTERS["en"] + QUESTION_STARTERS.get(lang, ())


def bare_interrogatives(lang: str) -> tuple[str, ...]:
    return BARE_INTERROGATIVES["en"] + BARE_INTERROGATIVES.get(lang, ())
