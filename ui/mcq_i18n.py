'''
this .py holds the Italian and French renderings of the prerequisite MCQ bank
that lives in prerequisite_check.py

prerequisite_check.MCQ_BANK stays the canonical bank. it is what
test_pipeline.py asserts against and what the prerequisite trigger evaluation in
the evaluation is measured on, so it is left untouched and this module supplies
display text only, question stems, option text and explanations. the answer key
never comes from here

that separation buys a property worth stating in the evaluation chapter: a
translation defect cannot change a student's score. score_responses() and
prerequisite_passed() work on the option labels A to D, which are identical in
every language, so an Italian student and an English student answering the same
way are scored the same by construction rather than by convention

if a translation is missing, malformed, or its option labels have drifted from
the canonical bank, localised_questions() falls back to the English item for
that question alone. the student sees one question in English rather than an
error and the probe still finishes

protocol names, acronyms and state names (ARP, SYN-ACK, ESTABLISHED, LISTEN,
default deny) are left in English throughout, matching the constraint put on
generated answers in i18n.answer_language_instruction(). those are the terms in
the module's slides, knowledge checks and exam paper, and a student revising in
Italian still sits an exam written in English. where the English term is also
the ordinary technical term in the target language the native gloss is given
once in brackets, HALF-OPEN (semiaperta), and the English form used after that
'''

from __future__ import annotations

from core.prerequisite_check import MCQ_BANK

#Translations Indexed [language][topic][question index].

MCQ_TRANSLATIONS: dict[str, dict[str, list[dict]]] = {

    #==========================================================================
    #Italian
    #==========================================================================
    "it": {
        "ARP protocol": [
            {
                "question": "Che cosa fa l'Address Resolution Protocol (ARP)?",
                "options": {
                    "A": "Associa i nomi di dominio agli indirizzi IP",
                    "B": "Associa gli indirizzi IP agli indirizzi MAC",
                    "C": "Associa gli indirizzi MAC ai numeri di porta",
                    "D": "Cifra il traffico tra due host",
                },
                "explanation": (
                    "ARP risolve un indirizzo IP noto (Livello 3) nell'indirizzo MAC "
                    "(Livello 2) dell'host che lo possiede, così che un frame possa "
                    "essere effettivamente indirizzato sulla rete locale. Associare i "
                    "nomi di dominio agli indirizzi IP è compito del DNS, non di ARP, e "
                    "ARP non fornisce alcuna cifratura. È proprio questa assenza di "
                    "autenticazione e cifratura che l'ARP spoofing sfrutta."
                ),
            },
            {
                "question": (
                    "ARP è definito un protocollo stateless. Che cosa significa questo "
                    "rispetto al modo in cui gestisce le risposte?"
                ),
                "options": {
                    "A": "Funziona solo su reti cablate",
                    "B": "Scarta le risposte che arrivano fuori ordine",
                    "C": "Accetta e sovrascrive le voci della cache anche senza una richiesta precedente",
                    "D": "Richiede l'autenticazione prima di aggiornare la cache",
                },
                "explanation": (
                    "Stateless significa che ARP non tiene traccia delle richieste che "
                    "ha inviato, quindi non può distinguere una risposta sollecitata da "
                    "una non sollecitata. Un host accetta una risposta ARP che non ha "
                    "mai chiesto e con essa sovrascrive una voce esistente della cache, "
                    "anche prima che questa sia scaduta. È esattamente questa proprietà "
                    "che l'attaccante sfrutta: la risposta falsificata non deve vincere "
                    "una corsa né attendere una richiesta, le basta arrivare."
                ),
            },
            {
                "question": (
                    "Dove memorizza un host le associazioni IP-MAC apprese dalle "
                    "risposte ARP?"
                ),
                "options": {
                    "A": "Nella cache del resolver DNS",
                    "B": "Nella tabella di routing",
                    "C": "Nella cache ARP (tabella ARP)",
                    "D": "Nell'insieme di regole del firewall",
                },
                "explanation": (
                    "Le associazioni apprese sono conservate nella cache ARP, detta "
                    "anche tabella ARP. Le voci scadono dopo circa 40 secondi, ed è per "
                    "questo che un attaccante deve continuare a reinviare risposte "
                    "falsificate per mantenere l'attacco. La tabella di routing contiene "
                    "le decisioni di next-hop per l'inoltro di Livello 3 ed è una "
                    "struttura del tutto diversa. L'espressione «avvelenare la cache "
                    "ARP» nomina proprio questa tabella."
                ),
            },
        ],

        "TCP handshake": [
            {
                "question": "Qual è la sequenza corretta dell'handshake TCP a tre vie?",
                "options": {
                    "A": "SYN, ACK, SYN-ACK",
                    "B": "SYN, SYN-ACK, ACK",
                    "C": "ACK, SYN, SYN-ACK",
                    "D": "SYN-ACK, SYN, FIN",
                },
                "explanation": (
                    "Il client invia SYN, il server risponde SYN-ACK e il client "
                    "conferma con ACK. L'ordine è importante per capire il SYN "
                    "flooding: il server impegna risorse nel momento in cui invia il "
                    "SYN-ACK, cioè prima che il client abbia dimostrato di esistere. È "
                    "questa asimmetria, in cui il server paga per primo, a costituire "
                    "l'intera base dell'attacco."
                ),
            },
            {
                "question": (
                    "In quale stato si trova una connessione dopo che il server ha "
                    "ricevuto il SYN iniziale ma prima che arrivi l'ACK finale del "
                    "client?"
                ),
                "options": {
                    "A": "ESTABLISHED",
                    "B": "CLOSED",
                    "C": "HALF-OPEN (semiaperta)",
                    "D": "LISTEN",
                },
                "explanation": (
                    "La connessione è semiaperta (HALF-OPEN): il server ha allocato lo "
                    "stato e inviato il proprio SYN-ACK, ma l'handshake non è completo. "
                    "Diventa ESTABLISHED solo all'arrivo dell'ACK finale. LISTEN è lo "
                    "stato in cui si trova il socket prima di ricevere qualsiasi SYN. Un "
                    "SYN flood funziona creando un gran numero di connessioni "
                    "semiaperte che non si completano mai."
                ),
            },
            {
                "question": (
                    "Quale risorsa mira a esaurire sul server un attacco TCP SYN flood?"
                ),
                "options": {
                    "A": "Lo spazio di archiviazione su disco",
                    "B": "Le voci della cache DNS",
                    "C": "I cicli di CPU usati per la cifratura",
                    "D": "La tabella delle connessioni che contiene le connessioni semiaperte",
                },
                "explanation": (
                    "Ogni connessione semiaperta occupa una voce nella tabella delle "
                    "connessioni del server. La tabella è finita, quindi una volta piena "
                    "i SYN legittimi vengono rifiutati e il servizio è negato. Da notare "
                    "che l'attacco non richiede né banda elevata né calcolo pesante: "
                    "colpisce una struttura di contabilità, non la capacità grezza, ed è "
                    "per questo che un attaccante con mezzi modesti può mettere in "
                    "difficoltà un server di grandi dimensioni."
                ),
            },
        ],

        "packet filter firewall": [
            {
                "question": (
                    "Un firewall a filtraggio di pacchetti prende le sue decisioni di "
                    "filtraggio in base a quale dei seguenti elementi?"
                ),
                "options": {
                    "A": "Solo le intestazioni dei singoli pacchetti, senza tracciare lo stato della connessione",
                    "B": "L'intero contenuto dei payload di livello applicativo",
                    "C": "Se una connessione è presente nella tabella di stato del firewall",
                    "D": "L'account utente associato al pacchetto",
                },
                "explanation": (
                    "Un filtro di pacchetti ispeziona le intestazioni di ogni pacchetto "
                    "isolatamente: indirizzo di origine e di destinazione, porta e "
                    "protocollo. Non conserva memoria di ciò che è avvenuto prima, "
                    "quindi non può sapere se un pacchetto appartiene a una "
                    "conversazione avviata dall'host. L'opzione C descrive un firewall "
                    "stateful e la B un proxy di livello applicativo. La distinzione "
                    "conta perché è proprio questa cecità al contesto che l'ispezione "
                    "stateful è stata introdotta a risolvere."
                ),
            },
            {
                "question": (
                    "In un insieme di regole di filtraggio dei pacchetti, che cosa "
                    "accade a un pacchetto che non corrisponde ad alcuna regola quando "
                    "la politica è «default deny»?"
                ),
                "options": {
                    "A": "Il pacchetto viene inoltrato e registrato nei log",
                    "B": "Il pacchetto viene restituito al mittente con un errore",
                    "C": "Il pacchetto viene scartato",
                    "D": "Il pacchetto viene messo in coda per una revisione manuale",
                },
                "explanation": (
                    "«Default deny» significa che tutto ciò che non è esplicitamente "
                    "permesso viene scartato: è l'impostazione predefinita più sicura, "
                    "perché una regola che ci si è dimenticati di scrivere fallisce in "
                    "chiusura anziché in apertura. La politica opposta, «default "
                    "permit», inoltra tutto ciò che non è esplicitamente bloccato. Le "
                    "regole sono valutate dall'alto verso il basso e l'azione "
                    "predefinita si applica solo quando nessuna regola ha corrisposto."
                ),
            },
            {
                "question": (
                    "Quale limite di un filtro di pacchetti stateless viene risolto da "
                    "un firewall stateful?"
                ),
                "options": {
                    "A": "I firewall stateless non possono ispezionare gli indirizzi IP di origine",
                    "B": "I firewall stateless devono lasciare aperte in ingresso tutte le porte alte per il traffico di ritorno, creando una vulnerabilità",
                    "C": "I firewall stateless possono filtrare solo UDP, non TCP",
                    "D": "I firewall stateless richiedono un proxy separato per ogni applicazione",
                },
                "explanation": (
                    "Poiché un filtro stateless non può riconoscere il traffico di "
                    "ritorno come appartenente a una connessione avviata dall'host, "
                    "permettere il normale traffico TCP in uscita lo costringe a "
                    "lasciare aperto in ingresso l'intero intervallo di porte effimere "
                    "(1024-65535). È una superficie esposta molto ampia. Un firewall "
                    "stateful traccia le connessioni in una tabella di stato, quindi può "
                    "ammettere un pacchetto in ingresso solo perché corrisponde a una "
                    "sessione già stabilita, mantenendo chiuse quelle porte in tutti gli "
                    "altri casi."
                ),
            },
        ],
    },

    #==========================================================================
    #French
    #==========================================================================
    "fr": {
        "ARP protocol": [
            {
                "question": "Que fait le protocole ARP (Address Resolution Protocol) ?",
                "options": {
                    "A": "Il associe les noms de domaine aux adresses IP",
                    "B": "Il associe les adresses IP aux adresses MAC",
                    "C": "Il associe les adresses MAC aux numéros de port",
                    "D": "Il chiffre le trafic entre deux hôtes",
                },
                "explanation": (
                    "ARP résout une adresse IP connue (couche 3) en l'adresse MAC "
                    "(couche 2) de l'hôte qui la détient, afin qu'une trame puisse "
                    "réellement être adressée sur le réseau local. Associer les noms de "
                    "domaine aux adresses IP relève du DNS, pas d'ARP, et ARP n'offre "
                    "aucun chiffrement. C'est précisément cette absence "
                    "d'authentification et de chiffrement qu'exploite l'usurpation ARP."
                ),
            },
            {
                "question": (
                    "ARP est décrit comme un protocole sans état (stateless). "
                    "Qu'est-ce que cela signifie quant à sa gestion des réponses ?"
                ),
                "options": {
                    "A": "Il ne fonctionne que sur les réseaux filaires",
                    "B": "Il rejette les réponses qui arrivent dans le désordre",
                    "C": "Il accepte et écrase les entrées du cache même sans requête préalable",
                    "D": "Il exige une authentification avant de mettre à jour le cache",
                },
                "explanation": (
                    "Sans état signifie qu'ARP ne garde aucune trace des requêtes qu'il "
                    "a envoyées : il ne peut donc pas distinguer une réponse sollicitée "
                    "d'une réponse non sollicitée. Un hôte accepte une réponse ARP qu'il "
                    "n'a jamais demandée et écrase avec elle une entrée existante du "
                    "cache, avant même son expiration. C'est exactement cette propriété "
                    "qu'exploite l'attaquant : la réponse falsifiée n'a besoin ni de "
                    "gagner une course ni d'attendre une requête, il lui suffit "
                    "d'arriver."
                ),
            },
            {
                "question": (
                    "Où un hôte stocke-t-il les associations IP-MAC apprises des "
                    "réponses ARP ?"
                ),
                "options": {
                    "A": "Dans le cache du résolveur DNS",
                    "B": "Dans la table de routage",
                    "C": "Dans le cache ARP (table ARP)",
                    "D": "Dans le jeu de règles du pare-feu",
                },
                "explanation": (
                    "Les associations apprises sont conservées dans le cache ARP, aussi "
                    "appelé table ARP. Les entrées expirent au bout d'environ 40 "
                    "secondes, ce qui oblige l'attaquant à renvoyer sans cesse des "
                    "réponses falsifiées pour maintenir son attaque. La table de routage "
                    "contient les décisions de saut suivant pour le routage de couche 3 "
                    ": c'est une structure entièrement différente. L'expression "
                    "« empoisonner le cache ARP » désigne précisément cette table."
                ),
            },
        ],

        "TCP handshake": [
            {
                "question": "Quelle est la séquence correcte du handshake TCP à trois voies ?",
                "options": {
                    "A": "SYN, ACK, SYN-ACK",
                    "B": "SYN, SYN-ACK, ACK",
                    "C": "ACK, SYN, SYN-ACK",
                    "D": "SYN-ACK, SYN, FIN",
                },
                "explanation": (
                    "Le client envoie SYN, le serveur répond SYN-ACK et le client "
                    "confirme par ACK. L'ordre importe pour comprendre l'inondation SYN "
                    ": le serveur engage des ressources au moment où il envoie le "
                    "SYN-ACK, c'est-à-dire avant que le client n'ait prouvé son "
                    "existence. C'est cette asymétrie, où le serveur paie en premier, "
                    "qui constitue toute la base de l'attaque."
                ),
            },
            {
                "question": (
                    "Dans quel état se trouve une connexion après que le serveur a reçu "
                    "le SYN initial mais avant l'arrivée de l'ACK final du client ?"
                ),
                "options": {
                    "A": "ESTABLISHED",
                    "B": "CLOSED",
                    "C": "HALF-OPEN (semi-ouverte)",
                    "D": "LISTEN",
                },
                "explanation": (
                    "La connexion est semi-ouverte (HALF-OPEN) : le serveur a alloué "
                    "l'état et envoyé son SYN-ACK, mais le handshake est incomplet. Elle "
                    "ne passe à ESTABLISHED qu'à l'arrivée de l'ACK final. LISTEN est "
                    "l'état du socket avant la réception de tout SYN. Une inondation SYN "
                    "consiste à fabriquer un grand nombre de connexions semi-ouvertes "
                    "qui n'aboutissent jamais."
                ),
            },
            {
                "question": (
                    "Quelle ressource une attaque par inondation SYN (SYN flood) "
                    "cherche-t-elle à épuiser sur le serveur ?"
                ),
                "options": {
                    "A": "L'espace de stockage sur disque",
                    "B": "Les entrées du cache DNS",
                    "C": "Les cycles CPU utilisés pour le chiffrement",
                    "D": "La table des connexions qui stocke les connexions semi-ouvertes",
                },
                "explanation": (
                    "Chaque connexion semi-ouverte occupe une entrée dans la table des "
                    "connexions du serveur. Cette table est finie : une fois pleine, les "
                    "SYN légitimes sont refusés et le service est indisponible. À noter "
                    "que l'attaque ne nécessite ni bande passante élevée ni calcul "
                    "intensif : elle vise une structure de comptabilité et non la "
                    "capacité brute, ce qui explique qu'un attaquant aux moyens modestes "
                    "puisse affecter un grand serveur."
                ),
            },
        ],

        "packet filter firewall": [
            {
                "question": (
                    "Sur quoi un pare-feu à filtrage de paquets fonde-t-il ses "
                    "décisions de filtrage ?"
                ),
                "options": {
                    "A": "Uniquement les en-têtes de chaque paquet, sans suivre l'état de la connexion",
                    "B": "L'intégralité du contenu des charges utiles de la couche application",
                    "C": "La présence de la connexion dans la table d'état du pare-feu",
                    "D": "Le compte utilisateur associé au paquet",
                },
                "explanation": (
                    "Un filtre de paquets inspecte les en-têtes de chaque paquet "
                    "isolément : adresse source et destination, port et protocole. Il ne "
                    "conserve aucune mémoire de ce qui a précédé et ne peut donc pas "
                    "savoir si un paquet appartient à une conversation initiée par "
                    "l'hôte. L'option C décrit un pare-feu à état, et l'option B un "
                    "proxy applicatif. La distinction importe car c'est précisément cet "
                    "aveuglement au contexte que l'inspection à état est venue corriger."
                ),
            },
            {
                "question": (
                    "Dans un jeu de règles de filtrage de paquets, que devient un "
                    "paquet qui ne correspond à aucune règle lorsque la politique est "
                    "« default deny » ?"
                ),
                "options": {
                    "A": "Le paquet est transmis et journalisé",
                    "B": "Le paquet est renvoyé à l'expéditeur avec une erreur",
                    "C": "Le paquet est rejeté",
                    "D": "Le paquet est mis en file d'attente pour examen manuel",
                },
                "explanation": (
                    "« Default deny » signifie que tout ce qui n'est pas explicitement "
                    "autorisé est rejeté : c'est la politique par défaut la plus sûre, "
                    "car une règle que l'on a oublié d'écrire échoue en fermeture plutôt "
                    "qu'en ouverture. La politique inverse, « default permit », transmet "
                    "tout ce qui n'est pas explicitement bloqué. Les règles sont "
                    "évaluées de haut en bas et l'action par défaut ne s'applique que "
                    "si aucune règle n'a correspondu."
                ),
            },
            {
                "question": (
                    "Quelle limite d'un filtre de paquets sans état un pare-feu à état "
                    "corrige-t-il ?"
                ),
                "options": {
                    "A": "Les pare-feu sans état ne peuvent pas inspecter les adresses IP source",
                    "B": "Les pare-feu sans état doivent laisser ouverts en entrée tous les ports hauts pour le trafic de retour, ce qui crée une vulnérabilité",
                    "C": "Les pare-feu sans état ne peuvent filtrer que l'UDP, pas le TCP",
                    "D": "Les pare-feu sans état exigent un proxy distinct par application",
                },
                "explanation": (
                    "Parce qu'un filtre sans état ne peut pas reconnaître le trafic de "
                    "retour comme appartenant à une connexion initiée par l'hôte, "
                    "autoriser le trafic TCP sortant normal l'oblige à laisser ouverte "
                    "en entrée toute la plage de ports éphémères (1024-65535). C'est une "
                    "surface d'exposition considérable. Un pare-feu à état suit les "
                    "connexions dans une table d'état : il peut donc admettre un paquet "
                    "entrant au seul motif qu'il correspond à une session établie, et "
                    "garder ces ports fermés le reste du temps."
                ),
            },
        ],
    },
}


#Merge

def localised_questions(topic: str, lang: str) -> list[dict]:
    """
    Return the MCQs for a topic with display text in the requested language.

    The answer key is always taken from the canonical English bank, never from
    the translation, so scoring is identical across languages by construction.
    A question whose translation is missing or whose option labels have drifted
    from the canonical set falls back to English individually, so one bad entry
    degrades a single item rather than the whole probe.
    """
    canonical = MCQ_BANK.get(topic, [])
    if lang == "en":
        return canonical

    overlay = MCQ_TRANSLATIONS.get(lang, {}).get(topic, [])
    merged: list[dict] = []

    for index, question in enumerate(canonical):
        translated = overlay[index] if index < len(overlay) else None

        if not translated or set(translated.get("options", {})) != set(question["options"]):
            merged.append(question)
            continue

        merged.append({
            "question":    translated["question"],
            "options":     translated["options"],
            "answer":      question["answer"],          #canonical, never translated
            "explanation": translated.get("explanation", question["explanation"]),
        })

    return merged


def localised_review(review: list[dict], topic: str, lang: str) -> list[dict]:
    """
    Re-render a completed probe's feedback in the requested language.

    build_review() in prerequisite_check.py works from the canonical bank and
    returns English text. Rather than duplicate its correctness logic here, its
    output is taken as given and only the human-readable fields are swapped for
    their translations. Correctness, the chosen label and the answer label pass
    through untouched.

    This also means a student who switches language after answering sees the
    review they already have re-rendered, rather than losing it.
    """
    if lang == "en":
        return review

    questions = localised_questions(topic, lang)
    if len(questions) != len(review):
        return review

    localised: list[dict] = []
    for item, question in zip(review, questions):
        localised.append({
            **item,
            "question":    question["question"],
            "chosen_text": question["options"].get(
                item["chosen_label"], item["chosen_text"]
            ),
            "answer_text": question["options"].get(
                item["answer_label"], item["answer_text"]
            ),
            "explanation": question["explanation"],
        })
    return localised
