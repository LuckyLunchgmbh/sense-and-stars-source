"""Original German lessons for the local SoulFlow learning workspace.

The week value is a stable display order, never a calendar or access restriction.
Only editorial content lives here; publication and account state belong to the
learning service. Quiz answer keys are backend data and must be stripped by its
public serializer. Importing this module never retrieves a source or starts work.

Public primary sources were checked on 20 October 2026. Astrodienst's article
text was available in the search index; direct requests encountered its browser
check. The other cited public pages were opened directly. Their bounded roles
are recorded per lesson; the examples and exercises are original SoulFlow work,
not course reproductions, translations, endorsements or a certified curriculum.
"""
from textwrap import dedent


def _text(value: str) -> str:
    return dedent(value).strip()


def _question(question_id: str, question: str, options: list[str], correct: int) -> dict:
    return {"id": question_id, "question": question, "options": options,
            "correct_index": correct}


ASTRO_INTRO = "https://www.astro.com/astrology/in_intro_e.htm"
ASTRO_ELEMENTS = "https://www.astro.com/astrology/in_elements_e.htm"
ASTRO_HOUSES = "https://www.astro.com/astrology/in_house2_e.htm"
ASTRO_ASPECTS = "https://www.astro.com/astrology/in_aspect_e.htm"
ASTRO_ASCENDANT = "https://www.astro.com/astrowiki/en/AC"
JONES_INTERVIEW = "https://markjonesastrology.com/blog/therapeutic-potential-astrology/"
JONES_VIDEOS = "https://markjonesastrology.com/free-videos/"
SCHAEFER_CURRICULUM = "https://www.silkeschaefer.com/astrologie-schule/grundausbildung"
WHO_GUIDE = "https://www.paho.org/en/documents/doing-what-matters-times-stress-illustrated-guide"


WORKSPACE_LESSONS = (
    {
        "seed_key": "workspace_symbolgrammatik_v1",
        "week": 5,
        "title": "Zeichen, Planeten und Häuser: einen Satz aus Symbolen bauen",
        "category": "Astrologische Grundlagen",
        "track": "Astrologische Sprache",
        "level": "foundation",
        "summary": "Eine lesbare Symbolgrammatik mit einem erfundenen Alltagsfall: Funktion, Ausdrucksweise und Lebensbereich unterscheiden.",
        "learning_objective": "Du kannst Planet, Zeichen und Haus getrennt benennen und aus ihrer Kombination mehrere offene Reflexionsfragen entwickeln. Vorkenntnisse sind nicht erforderlich.",
        "body": _text("""
            Ein Radix ist zunächst eine berechnete Darstellung des Himmels für einen Ort und
            Zeitpunkt. Die astrologische Deutung fügt eine symbolische Lesart hinzu. In diesem
            Lernraum behandeln wir diese Lesart als spirituelles Reflexionsmodell. Die drei
            Fragen unserer eigenen Lernhilfe lauten: Welche Funktion steht im Mittelpunkt?
            Wie könnte sie sich ausdrücken? In welchem Lebensbereich möchten wir darüber
            nachdenken? Planet, Zeichen und Haus beantworten verschiedene Fragen.

            Als kleines Arbeitsvokabular verwenden wir folgende konventionelle Zuordnungen:
            Sonne für bewusste Ausrichtung, Mond für vertraute Bedürfnisse, Merkur für
            Denken und Verständigung, Venus für Werte und Verbundenheit, Mars für Handeln
            und Durchsetzung. Jupiter steht hier für Erweiterung, Saturn für Struktur,
            Uranus für Erneuerung, Neptun für Sehnsucht und Vorstellung, Pluto für tiefen
            Wandel. Diese Wörter sind Einstiegshilfen, keine vollständigen Definitionen.
            Sonne und Mond heißen in der astrologischen Fachsprache auch Lichter; astronomisch
            sind sie ein Stern und ein natürlicher Satellit, keine Planeten.

            Zeichen beschreiben in dieser Grammatik die Ausdrucksweise, Häuser einen
            Erfahrungsbereich. Die zwölf Hausfelder lassen sich zum Einstieg mit Auftreten,
            Ressourcen, Austausch, Herkunft, Gestaltung, Alltag, Gegenüber, gemeinsam
            Geteiltem, Horizonterweiterung, öffentlichem Wirken, Gemeinschaft und Rückzug
            verbinden. Diese Stichwörter sind eine eigene vereinfachte Lernkarte westlicher
            Konventionen. Haus drei ist beispielsweise kein Synonym für das Zeichen Zwillinge:
            Lebensbereich und Ausdrucksweise bleiben unterscheidbar.

            Unser erfundenes Beispiel lautet Merkur in Jungfrau im dritten Haus. Wir
            verbinden Verständigung, sorgfältiges Unterscheiden und alltäglichen Austausch.
            Eine mögliche Frage wäre: Hilft dir eine genaue Gesprächsvorbereitung? Eine
            zweite: Wann macht das Überarbeiten eine Nachricht unnötig schwer? Eine dritte:
            Wo möchtest du bewusst einfacher sprechen? Die gleiche Kombination eröffnet
            unterschiedliche Gespräche. Keine dieser Fragen beweist, wie eine Person ist.

            Eine gute erste Deutung bleibt kurz genug, um beantwortet werden zu können.
            Wenn du zehn Eigenschaften aneinanderreihst, verliert dein Gegenüber die
            Möglichkeit, sich konkret darauf zu beziehen. Beginne mit einer Alltagsszene,
            höre die Antwort und lass daraus die nächste Frage entstehen.
        """),
        "exercise": _text("""
            Lege drei Zettel mit den Überschriften Funktion, Ausdruck und Lebensbereich vor
            dich. Schreibe auf die erste Reihe Merkur, Jungfrau und drittes Haus. Formuliere
            dazu einen einzigen Satz, der mit „Eine mögliche Lesart wäre …“ beginnt. Erfinde
            anschließend eine Szene: Jemand schreibt eine Einladung und verbessert sie
            mehrfach. Beschreibe eine hilfreiche und eine anstrengende Möglichkeit derselben
            Symbolkombination. Wechsle danach nur den Lebensbereich zu Haus elf, also
            Gemeinschaft. Wie verändert sich deine Frage? Lies beide Fassungen laut und
            streiche jede Behauptung, die eine unbekannte Person festlegt. Bewahre die
            beiden unterschiedlichen Fragen als erste Notiz auf. Dafür brauchst du weder
            echte Geburtsdaten noch einen vollständigen Deutungstext.
        """),
        "reflection_prompt": "Welche deiner Fragen lädt zu einer konkreten Erfahrung ein? Wo hast du Planet, Zeichen und Haus noch vermischt, und welches Beispiel macht den Unterschied für dich anschaulich?",
        "content_version": 1,
        "source_url": ASTRO_INTRO,
        "source_title": "Astrodienst: A Brief Introduction to Astrology",
        "source_note": "Quelle belegt: Astrodienst: A Brief Introduction to Astrology (" + ASTRO_INTRO + ") führt Planeten, Zeichen, Häuser und ihre Beziehungen als astrologische Grundbegriffe ein. Die Zuordnungen werden hier als Konventionen behandelt. Symbolsatz, Lernkarte, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Prüfstand 20.10.2026; kein Wirksamkeitsbeleg.",
        "quiz": [
            _question("symbols_function", "Welcher Baustein bezeichnet in der Lernhilfe die Funktion?",
                      ["Haus", "Planet", "Zeichen"], 1),
            _question("symbols_alternatives", "Was ist ein sinnvoller nächster Schritt nach einem Symbolsatz?",
                      ["Eine offene Frage zu einer konkreten Erfahrung stellen", "Die gesamte Biografie daraus ableiten", "Eine Charaktereigenschaft verbindlich feststellen"], 0),
        ],
    },
    {
        "seed_key": "workspace_elemente_qualitaeten_v1",
        "week": 6,
        "title": "Elemente und Qualitäten: zwölf Zeichen mit zwei Blickwinkeln",
        "category": "Astrologische Grundlagen",
        "track": "Astrologische Sprache",
        "level": "foundation",
        "summary": "Die vier Elemente und drei Qualitäten als symbolische Kombination verstehen und an einer eigenen Alltagsszene erproben.",
        "learning_objective": "Du kannst die zwölf Zeichen ihren Elementen und Qualitäten zuordnen und eine Symbolkategorie von einer persönlichen Fähigkeit unterscheiden. Vorwissen: die drei Bausteine der Symbolgrammatik.",
        "body": _text("""
            Elemente und Qualitäten bilden zwei verschiedene Ordnungen derselben zwölf
            Zeichen. In westlicher Astrologie gehören Widder, Löwe und Schütze zum Feuer;
            Stier, Jungfrau und Steinbock zur Erde; Zwillinge, Waage und Wassermann zur
            Luft; Krebs, Skorpion und Fische zum Wasser. Die zweite Ordnung lautet kardinal,
            fix und veränderlich. Kardinal sind Widder, Krebs, Waage und Steinbock; fix sind
            Stier, Löwe, Skorpion und Wassermann; veränderlich sind Zwillinge, Jungfrau,
            Schütze und Fische. Jede Kombination kommt genau einmal vor.

            Wir nutzen die Elemente als vier eigene Arbeitsfragen: Was entzündet meine
            Begeisterung? Was lässt sich praktisch tragen? Welche Gedanken möchten in
            Austausch kommen? Was nehme ich an Empfindungen wahr? Das sind symbolische
            Blickwinkel, keine naturwissenschaftlichen Stoffklassen des Menschen. Auch
            jemand ohne hervorgehobene Wasserzeichen kann mitfühlend handeln. Eine gezählte
            Zeichenverteilung misst weder Empathie noch Begabung.

            Die Qualitäten machen die gleiche Szene beweglich. Kardinal fragt nach dem
            Beginn, fix nach dem Bewahren, veränderlich nach dem Anpassen. Stell dir ein
            gemeinsames Abendessen vor. Jemand schlägt den Termin vor, jemand hält die
            Verabredung zusammen, jemand verändert das Menü, weil ein Gast später kommt.
            Alle drei Tätigkeiten sind nützlich. Eine Person kann sie nacheinander übernehmen.
            Unsere Alltagsszene ist eine selbst entwickelte Lernhilfe, kein Test zur
            Ermittlung eines angeblich wahren Temperaments.

            Jetzt kombiniere beide Ordnungen. Löwe ist fixes Feuer, also könnte die
            Lernfrage nach beständiger Begeisterung für ein kreatives Vorhaben lauten.
            Jungfrau ist veränderliche Erde: Wie lässt sich eine praktische Vorgehensweise
            verbessern? Wassermann ist fixe Luft, obwohl sein Name Wasser enthält. Für
            einen Lernabend könntest du hier fragen, welche Idee eine Gruppe zusammenhält.
            Das sind bewusst gewählte Fragen, keine fertigen Personenbeschreibungen.

            Beim Lesen eines ganzen Radix zählt außerdem, welche Faktoren du überhaupt
            einbeziehst. Verschiedene Gewichtungen ergeben unterschiedliche Schwerpunkte.
            Schreibe deshalb deine gewählte Zählweise dazu. Für den Anfang reicht es,
            die Kategorien sicher zu unterscheiden und anhand eines Beispiels zu erklären,
            statt eine Prozentzahl als Identität auszugeben.
        """),
        "exercise": _text("""
            Zeichne ein Raster mit vier Elementspalten und drei Qualitätszeilen. Trage die
            zwölf Zeichen zunächst aus dem Gedächtnis ein und prüfe dann mit dem Lehrtext.
            Wähle drei Felder, die dich neugierig machen. Entwirf zu jedem Feld eine andere
            Art, denselben Lernnachmittag zu gestalten: etwa anfangen, vertiefen oder den
            Ablauf ändern. Schreibe jeweils eine konkrete Handlung auf, die höchstens zehn
            Minuten dauert. Probiere eine davon aus. Notiere danach, was du tatsächlich
            gemacht hast, unabhängig davon, welches Zeichen du dir vorher zugeordnet
            hättest. Unterstreiche eine Fähigkeit, die du in mehreren Feldern einsetzen
            konntest. So wird aus einer Merkliste ein bewegliches Arbeitsmodell.
        """),
        "reflection_prompt": "Welche Kombination war leicht zu merken, welche hat dich überrascht? Wie hat dein praktischer Versuch gezeigt, dass eine symbolische Kategorie eine Person nicht auf eine einzige Verhaltensweise begrenzt?",
        "content_version": 1,
        "source_url": ASTRO_ELEMENTS,
        "source_title": "Astrodienst: The four Elements and the Signs",
        "source_note": "Quelle belegt: Astrodienst: The four Elements and the Signs (" + ASTRO_ELEMENTS + ") dokumentiert die traditionelle Element- und Qualitätszuordnung. Die Seite ist eine astrologische Grundlagenquelle, keine validierte Persönlichkeitsmessung. Rasteranwendung, Abendessen, Arbeitsfragen, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Prüfstand 20.10.2026.",
        "quiz": [
            _question("elements_water", "Welche Zeichen gehören konventionell zum Wasser?",
                      ["Zwillinge, Waage, Wassermann", "Widder, Löwe, Schütze", "Krebs, Skorpion, Fische"], 2),
            _question("qualities_fixed", "Welche vier Zeichen sind fix?",
                      ["Stier, Löwe, Skorpion, Wassermann", "Widder, Krebs, Waage, Steinbock", "Zwillinge, Jungfrau, Schütze, Fische"], 0),
            _question("elements_capacity", "Was lässt sich aus fehlenden Wasserzeichen sicher schließen?",
                      ["Die Person kann nicht mitfühlen", "Nur, dass nach der gewählten Zählweise dort kein berücksichtigter Faktor liegt", "Die Person sollte keine Gespräche führen"], 1),
        ],
    },
    {
        "seed_key": "workspace_sonne_mond_asc_v1",
        "week": 7,
        "title": "Sonne, Mond und Aszendent: drei Fragen an dieselbe Szene",
        "category": "Astrologische Grundlagen",
        "track": "Radix verstehen",
        "level": "foundation",
        "summary": "Ausrichtung, vertraute Bedürfnisse und Auftreten zusammen betrachten; die Empfindlichkeit des Aszendenten gegenüber Geburtszeit und Ort verstehen.",
        "learning_objective": "Du formulierst drei unterscheidbare Reflexionsfragen und erkennst, wann eine ungeklärte Geburtszeit die Arbeit mit Aszendent und Häusern begrenzt. Vorwissen: Zeichen und Planeten unterscheiden.",
        "body": _text("""
            Wer nur das Sonnenzeichen kennt, sieht einen einzelnen Faktor. Für unsere
            eigene Lernhilfe nutzen wir Sonne, Mond und Aszendent als drei unterschiedliche
            Fragen an eine Alltagsszene. Die Sonne fragt nach bewusster Ausrichtung: Was
            möchte ich gestalten? Der Mond fragt nach vertrauten Bedürfnissen: Was hilft
            mir, mich in einer Situation zurechtzufinden? Der Aszendent fragt nach dem
            Eintritt in die Situation: Wie gehe ich auf die Welt zu? Diese Fragen sind
            ein redaktionelles Reflexionsangebot innerhalb astrologischer Konventionen.

            Astronomisch ist der Aszendent der Schnittpunkt der Ekliptik mit dem östlichen
            Horizont. Er hängt von Zeitpunkt und Ort ab und ist kein weiterer Planet.
            Geburtszeit, historische Zeitzone und gegebenenfalls Sommerzeit gehören deshalb
            zur Datenprüfung. Eine nur ungefähr erinnerte Uhrzeit darf nicht durch die
            Deutung scheinbar genau werden. In vielen Häusersystemen hängt auch die
            Hausverteilung von diesen Angaben ab.

            Betrachte unseren erfundenen Fall einer Person, die zum ersten Mal einen
            kleinen Zeichenkurs anbietet. Eine Sonnenfrage wäre: Welche Art des Gestaltens
            ist mir heute wichtig? Die Mondfrage könnte lauten: Brauche ich vorher Ruhe,
            eine vertraute Person oder eine klare Reihenfolge? Beim Aszendenten fragen
            wir: Wie möchte ich den ersten Kontakt gestalten? Die Antworten können
            unterschiedlich sein und sich trotzdem ergänzen. Wer etwas zeigen möchte,
            kann zugleich einen ruhigen Einstieg brauchen.

            Du kannst diese Szene zunächst ohne Zeichenangaben untersuchen. Danach setzt
            du versuchsweise symbolische Farben hinzu: Sonne im Löwen als Frage nach
            sichtbarer Gestaltung, Mond im Stier als Frage nach einem verlässlichen
            Rahmen, Aszendent Zwillinge als Frage nach neugierigem Kontakt. Dieses
            didaktische Beispiel ist keine berechnete Geburtskarte. Es soll zeigen, wie
            mehrere Motive nebeneinander Platz finden, statt einander aufzuheben.

            Wenn die Uhrzeit fehlt, bleibst du bei dem, was du verantwortbar betrachten
            kannst. Auch die Mondposition kann an einem Tag das Zeichen wechseln; prüfe
            im tatsächlichen Rechenergebnis die Unsicherheit. Eine ehrliche Leerstelle
            ist eine brauchbare Information. Du brauchst keinen geratenen Aszendenten,
            um eine konkrete Frage nach Vorbereitung und Begegnung zu stellen.
        """),
        "exercise": _text("""
            Wähle eine unverfängliche bevorstehende Situation, beispielsweise einen Besuch
            oder ein kreatives Vorhaben. Schreibe je einen Satz zu Ausrichtung, vertrautem
            Bedürfnis und erstem Kontakt. Entwirf anschließend einen Ablauf, der alle drei
            berücksichtigt: etwa zuerst den Raum vorbereiten, dann ein Bild zeigen und
            mit einer offenen Frage beginnen. Vergleiche zwei Datenkarten: A enthält eine
            dokumentierte Ortszeit samt geklärter Zeitzone; B nur „am Vormittag“. Notiere,
            welche Aussagen zum Aszendenten du bei B offenlassen musst. Nutze keine echten
            fremden Geburtsdaten. Wenn du ein eigenes Radix verwendest, halte die Herkunft
            der Uhrzeit fest und übernimm Unsicherheiten sichtbar in deine Notiz.
        """),
        "reflection_prompt": "Welche deiner drei Fragen hat eine neue Handlungsidee eröffnet? Wie verändert sich deine Sprache, wenn du zu einer Geburtszeit nur eine ungefähre Angabe statt eines verlässlichen Nachweises hast?",
        "content_version": 1,
        "source_url": ASTRO_ASCENDANT,
        "source_title": "Astrodienst Astrowiki: Ascendant",
        "source_note": "Quelle belegt: Astrodienst Astrowiki: Ascendant (" + ASTRO_ASCENDANT + ") erklärt die Geometrie und Orts-/Zeitabhängigkeit des Aszendenten. Ergänzender Grundlagenlink: Astrodienst: The Houses (" + ASTRO_HOUSES + "). Die drei Lernfragen, der Zeichenkurs, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quellen, Prüfstand 20.10.2026; keine Berechnung eines realen Radix in diesem Beispiel.",
        "quiz": [
            _question("asc_geometry", "Was bezeichnet der Aszendent astronomisch?",
                      ["Die Mitte der Sonne", "Der Schnittpunkt von Ekliptik und östlichem Horizont", "Den Abstand zwischen Mars und Venus"], 1),
            _question("asc_uncertain", "Welche Vorgehensweise passt bei ungeklärter Geburtszeit?",
                      ["Den passenden Aszendenten nach Charakter auswählen", "Mittag als gesicherte Geburtszeit übernehmen", "Aszendent und Häuser offenlassen, bis Zeit und Zeitzone geklärt sind"], 2),
        ],
    },
    {
        "seed_key": "workspace_aspekte_synthese_v1",
        "week": 8,
        "title": "Aspekte und Synthese: aus Einzelteilen ein offenes Gespräch machen",
        "category": "Astrologische Grundlagen",
        "track": "Radix verstehen",
        "level": "foundation",
        "summary": "Winkel und Orben nachvollziehen, anschließend einen kleinen Zusammenhang mit mehreren möglichen Ausdrucksformen formulieren.",
        "learning_objective": "Du erkennst die fünf Hauptaspekte, berechnest in einem einfachen Beispiel den Orbis und verbindest Faktoren zu einer prüfbaren Gesprächsfrage. Vorwissen: Symbolgrammatik und Elemente.",
        "body": _text("""
            Aspekte sind ausgewählte Winkelbeziehungen zwischen Horoskopfaktoren entlang
            des Tierkreises. Die fünf hier verwendeten Hauptaspekte heißen Konjunktion
            mit 0°, Sextil mit 60°, Quadrat mit 90°, Trigon mit 120° und Opposition mit
            180°. Der Orbis bezeichnet die Abweichung vom exakten Winkel. Liegen zwei
            Faktoren 92° auseinander, beträgt die Abweichung zum Quadrat 2°. Welcher
            Orbis zugelassen wird, hängt von Schule, Faktoren und verwendeter Regel ab.
            Eine farbige Linie allein erklärt diese Regel nicht.

            Die Geometrie ist berechenbar; ihre persönliche Bedeutung wird gedeutet.
            Für unsere eigene Lernhilfe nehmen wir das Quadrat als Frage nach Reibung,
            das Trigon als Frage nach leicht verfügbarem Zusammenspiel und die Opposition
            als Frage nach zwei Polen. Das sind symbolische Gesprächsöffner. Ein Quadrat
            ist kein schlechtes Schicksal, ein Trigon keine Garantie für gelebtes Können.
            Ein leicht verfügbares Muster kann auch unbemerkt bleiben.

            Stell dir zwei erfundene Arbeitsmotive vor: Venus steht in unserer Lesart
            für das Wertvolle, Saturn für tragende Form. Mit einer Quadratfrage könnte
            daraus werden: Wie vereinbarst du Freude am Gestalten mit deinem Anspruch,
            etwas zuverlässig fertigzustellen? In einem Fall hilft ein fester Termin,
            in einem anderen erstickt ein zu enger Plan die Freude. Die Antwort kommt
            aus der tatsächlichen Erfahrung, nicht aus dem Winkel allein.

            Synthese bedeutet hier, einen Zusammenhang zu bilden, der noch Raum für
            Widerspruch lässt. Beginne mit dem Anliegen, wähle wenige relevante Faktoren,
            benenne ihr Zusammenspiel und entwickle mindestens zwei Ausdrucksmöglichkeiten.
            Frage anschließend nach einer konkreten Szene. Wer zehn Deutungen sammelt,
            hat dadurch noch keinen Zusammenhang erklärt. Eine gute Synthese macht die
            nächste Frage leichter und die Behauptung kleiner.

            Für die Rechenübung gelten vereinbarte 3° als maximale Abweichung; das ist
            keine allgemeine Regel der App oder aller astrologischen Schulen. Halte
            Rechenregel, Symbollesart und Gesprächsergebnis in getrennten Sätzen fest.
            Dadurch kannst du später sehen, ob du einen Winkel falsch gelesen hast
            oder ob lediglich dein Deutungsvorschlag nicht zur Erfahrung passte.
        """),
        "exercise": _text("""
            Zeichne einen Kreis und prüfe drei voneinander unabhängige synthetische Paare
            mit Abständen von 58°, 92° und 124°. Ordne den jeweils nächsten Hauptaspekt
            zu und notiere die Abweichung. Entscheide nach der vereinbarten 3°-Regel,
            welche Paare du berücksichtigen würdest. Wähle danach nur das Quadratbeispiel
            und arbeite mit Venus und Saturn als Symbolwörtern. Entwirf zwei Alltagsszenen,
            in denen Freude und Verbindlichkeit verschieden zusammenwirken. Schreibe eine
            offene Rückfrage und eine kleine freiwillige Handlung dazu. Lies deine Synthese
            noch einmal ohne astrologische Begriffe: Bleibt verständlich, worüber die
            Person nachdenken könnte? Wenn nicht, vereinfache sie auf einen Zusammenhang.
        """),
        "reflection_prompt": "An welcher Stelle wechselst du von einer messbaren Winkelangabe zu einer symbolischen Lesart? Welche konkrete Antwort würde dich veranlassen, deine erste Synthese zu ändern oder ganz zu verwerfen?",
        "content_version": 1,
        "source_url": ASTRO_ASPECTS,
        "source_title": "Astrodienst: The Aspects",
        "source_note": "Quelle belegt: Astrodienst: The Aspects (" + ASTRO_ASPECTS + ") erläutert Hauptwinkel und Orben als astrologische Konventionen. Die Rechenaufgaben, vereinbarte 3°-Übungsregel, Synthesehilfe, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Prüfstand 20.10.2026; symbolische Bedeutung ist vom geometrischen Befund getrennt.",
        "quiz": [
            _question("aspects_orb", "Zwei Faktoren liegen 92° auseinander. Wie groß ist der Orbis zum exakten Quadrat?",
                      ["92°", "2°", "12°"], 1),
            _question("aspects_trine", "Welcher exakte Winkel gehört zum Trigon?",
                      ["60°", "90°", "120°"], 2),
            _question("aspects_synthesis", "Was macht eine offene Synthese aus?",
                      ["Wenige Faktoren, mehrere Möglichkeiten und eine konkrete Rückfrage", "Möglichst viele Eigenschaften ohne Zusammenhang", "Ein berechneter Winkel beweist eine Biografie"], 0),
        ],
    },
    {
        "seed_key": "workspace_spirituelle_entwicklung_v1",
        "week": 9,
        "title": "Spirituelle und evolutionäre Deutung: Entwicklung als offene Frage",
        "category": "Spirituelle Vertiefung",
        "track": "Spirituelle Deutung",
        "level": "deepening",
        "summary": "Seelenentwicklung als Lehrannahme kennenlernen und aus einer symbolischen Geschichte einen frei gewählten nächsten Schritt gewinnen.",
        "learning_objective": "Du unterscheidest spirituelle Annahme, astrologisches Symbol und selbst gewählte Bedeutung. Vorwissen: eine einfache Radix-Synthese; du musst keiner bestimmten spirituellen Schule zustimmen.",
        "body": _text("""
            Spirituelle Astrologie fragt nach Sinn und Verbundenheit. Evolutionäre
            Schulen betrachten ein Horoskop häufig unter dem Gesichtspunkt von
            Seelenentwicklung; Mondknoten und Pluto können dabei besondere Rollen
            erhalten. Mark Jones beschreibt in seinem öffentlichen Interview eine
            solche Entwicklungsperspektive. Das ist ein spiritueller Lehransatz, kein
            Nachweis früherer Leben oder einer vorbestimmten persönlichen Aufgabe.

            Für diese eigene Übung übersetzen wir Entwicklung in drei Fragen: Welches
            vertraute Muster erkenne ich selbst? Was möchte ich bewahren? Welche neue
            Möglichkeit möchte ich ausprobieren? Du kannst das Bild einer Seele
            verwenden, wenn es zu deinem Weltbild passt. Du kannst ebenso von Werten,
            Gewohnheiten oder einer Lebensgeschichte sprechen. Die Wahl der Sprache
            gehört zur Person, deren Erfahrung betrachtet wird.

            Unser erfundener Fall handelt von einer Hobbygärtnerin, die jedes Beet
            allein plant. Sie schätzt die Ruhe darin und möchte zugleich andere Menschen
            beteiligen. Ein spirituelles Bild könnte ein Tor im Garten sein: Es schützt
            einen wertvollen Raum und lässt sich für Gäste öffnen. Die Entwicklung liegt
            nicht darin, das Tor endgültig abzubauen. Sie könnte darin liegen, bewusst
            zu entscheiden, wann und für wen es offensteht. Dieses Bild stammt aus
            unserer Redaktion und ist keine überlieferte Methode eines Lehrenden.

            Wenn du ein astrologisches Symbol hinzunimmst, benenne seine Rolle. Ein
            Mondknoten ist einer der Punkte, an denen die Mondbahn die Ekliptik kreuzt, kein Planet.
            Seine Deutung als Entwicklungsrichtung ist eine weitere Ebene. Ebenso kann
            Pluto als Symbol tiefen Wandels gelesen werden, ohne zu behaupten, jemand
            müsse einen Verlust erleben, um wachsen zu dürfen. Weder Leid noch
            Schicksalsdruck sind Voraussetzungen unserer Übung.

            Verschiedene Schulen setzen andere Schwerpunkte. Eine sinnvolle Begegnung
            mit ihnen beginnt deshalb mit einer klaren Frage an die Methode: Welche
            Annahme wird verwendet, und was ermöglicht sie mir heute? Behalte auch die
            Möglichkeit, eine Deutung unbrauchbar zu finden. Eine selbst gewählte kleine
            Handlung ist für das Üben hilfreicher als eine große Aussage darüber,
            was deine Seele angeblich mit dir vorhat.
        """),
        "exercise": _text("""
            Nimm dir zehn ruhige Minuten und wähle ein gewöhnliches Vorhaben. Stell dir,
            wenn du möchtest, einen Garten mit einem Tor vor; alternativ zeichne zwei
            einfache Felder für Bewahren und Öffnen. Schreibe drei Dinge auf, die an
            deiner bisherigen Art wertvoll sind. Ergänze eine neue Möglichkeit. Lass
            beide Seiten im Bild vorkommen und wähle eine freiwillige Handlung für die
            nächsten Tage, etwa eine andere Person um eine Idee bitten. Formuliere
            danach denselben Schritt einmal in spiritueller und einmal in alltäglicher
            Sprache. Prüfe, welche Fassung dir mehr Entscheidungsfreiheit lässt. Du kannst
            die Bildübung jederzeit beenden und bei den geschriebenen Fragen bleiben.
        """),
        "reflection_prompt": "Welche Bedeutung hast du selbst gewählt, und welche hast du einer Lehrtradition entnommen? Was an deinem nächsten Schritt bleibt sinnvoll, wenn du die spirituelle Erklärung versuchsweise beiseitelässt?",
        "content_version": 1,
        "source_url": JONES_INTERVIEW,
        "source_title": "Mark Jones: The Therapeutic Potential of Astrology",
        "source_note": "Quelle belegt: Mark Jones: The Therapeutic Potential of Astrology (" + JONES_INTERVIEW + ") enthält Jones’ eigene evolutionäre Perspektive. Interview von 2015, auf seiner Website 2018 veröffentlicht; keine empirische Bestätigung von Seelenannahmen. Gartenbild, Lernfragen, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Prüfstand 20.10.2026; keine Übernahme des bezahlten Unterrichts.",
        "quiz": [
            _question("evolution_assumption", "Welchen Status hat Seelenentwicklung in dieser Lektion?",
                      ["Eine für alle Menschen bewiesene Tatsache", "Eine freiwillig verwendbare spirituelle Lehrannahme", "Eine verbindliche Diagnose"], 1),
            _question("evolution_choice", "Welche Frage lässt der Person Entscheidungsfreiheit?",
                      ["Welchen kleinen Schritt möchtest du selbst ausprobieren?", "Welches Leid hat deine Seele zwingend bestellt?", "Warum widersprichst du deiner vorgeschriebenen Aufgabe?"], 0),
        ],
    },
    {
        "seed_key": "workspace_selbstpraesenz_v1",
        "week": 10,
        "title": "Selbstpräsenz: vor der Deutung im eigenen Raum ankommen",
        "category": "Präsenz und Wahrnehmung",
        "track": "Präsenz und Selbstwahrnehmung",
        "level": "deepening",
        "summary": "Eine persönliche Ankommenspraxis entwickeln: Umgebung, Körperkontakt und eigenen Ausgangszustand wahrnehmen, ohne ein besonderes Erleben erzwingen zu müssen.",
        "learning_objective": "Du gestaltest eine kurze freiwillige Präsenzpraxis und hältst deinen Ausgangszustand fest. Vorkenntnisse sind nicht erforderlich; die Übung dient alltäglicher Aufmerksamkeit, nicht einer Behandlung.",
        "body": _text("""
            Präsenz beginnt mit dem Raum, in dem du tatsächlich sitzt. Vielleicht hörst
            du Straßenverkehr, bemerkst die Tischkante oder spürst den Kontakt deiner
            Füße zum Boden. Du musst diese Eindrücke nicht verändern. Für unser eigenes
            Lernritual genügt zunächst, drei konkrete Dinge zu bemerken und den nächsten
            bewussten Schritt zu wählen. Ein besonderer innerer Zustand ist keine
            Voraussetzung, um aufmerksam zuzuhören.

            Der öffentlich zugängliche WHO-Ratgeber „Doing What Matters in Times of
            Stress“ enthält Grounding-Übungen. Wir nehmen daraus ausschließlich den
            Bezug zu gegenwärtiger Aufmerksamkeit auf. Unser nachfolgendes Ankommensritual
            ist eine eigene Ausarbeitung für den Lernraum. Der Ratgeber belegt weder
            Energiefelder noch astrologische Wahrnehmung; wir verwenden ihn nicht als
            Begründung für solche Aussagen.

            Stell dir einen Nachmittag vor, an dem du schnell von einer Nachricht zur
            nächsten gewechselt hast. Vor einem Übungsgespräch bemerkst du, dass du noch
            auf eine Antwort wartest. Statt diese Spannung sofort als Resonanz mit dem
            Gegenüber zu verstehen, gibst du ihr einen eigenen Platz: „Ich bin noch bei
            meinem vorherigen Gespräch.“ Du schreibst einen kurzen Satz auf und richtest
            die Aufmerksamkeit dann auf den aktuellen Kontakt. Der Satz muss nicht
            verschwinden, damit du beginnen kannst.

            Wenn dir ein spirituelles Bild hilft, kannst du dir eine kleine Laterne
            vorstellen. Ihr Licht steht in dieser selbst entwickelten Übung für die
            Aufmerksamkeit, die du gerade zur Verfügung hast. Du entscheidest, wohin
            du es richtest. Die Laterne ist eine persönliche Vorstellung, kein Schutz,
            dessen Wirkung nachgewiesen wäre. Wer keine inneren Bilder mag, kann einen
            realen Gegenstand auf den Tisch legen und ihn als Erinnerungszeichen nutzen.

            Zum Ankommen gehört auch eine ehrliche Einschätzung deiner Bereitschaft.
            Vielleicht ist heute ein kurzes, klar begrenztes Gespräch passend. Vielleicht
            möchtest du eine Pause oder einen neuen Termin vereinbaren. Die Qualität
            dieser Praxis zeigt sich daran, ob du deinen Zustand genauer beschreiben
            und eine angemessene Entscheidung treffen kannst. Du musst weder Leere
            herstellen noch belastende Erinnerungen aufsuchen, um diese Lektion zu üben.
        """),
        "exercise": _text("""
            Wähle einen Sitzplatz und lass die Augen offen, wenn das für dich angenehm
            ist. Benenne leise drei Dinge im Raum, zwei Geräusche und einen Kontaktpunkt
            zum Stuhl oder Boden. Atme in deinem üblichen Rhythmus; du musst nichts
            vertiefen oder anhalten. Notiere in einfachen Worten, wie wach, beschäftigt
            oder ruhig du dich gerade erlebst. Wähle dann für eine Minute die Laterne
            als Vorstellung oder einen Gegenstand als Aufmerksamkeitszeichen. Beende
            bewusst mit einem Blick in den Raum. Schreibe einen Satz darüber, ob du
            jetzt beginnen, verkürzen oder pausieren möchtest. Wenn die Übung unangenehm
            wird, unterbrich sie und entscheide selbst, was gerade passt.
        """),
        "reflection_prompt": "Welche Beobachtung war schon vor einem Kontakt vorhanden? Hat dir ein reales Zeichen oder ein inneres Bild mehr geholfen, deine Aufmerksamkeit bewusst auszurichten und eine eigene Entscheidung zu treffen?",
        "content_version": 1,
        "source_url": WHO_GUIDE,
        "source_title": "PAHO/WHO: Doing What Matters in Times of Stress: An Illustrated Guide",
        "source_note": "Quelle belegt: PAHO/WHO: Doing What Matters in Times of Stress: An Illustrated Guide (" + WHO_GUIDE + "), 2020, stellt allgemeine Präsenz-/Grounding-Übungen bereit. Keine Quelle für spirituelle Felder oder Astro-Deutung. Laternenbild, Ausgangsnotiz, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Prüfstand 20.10.2026; keine therapeutische Anleitung oder Wirkungszusage.",
        "quiz": [
            _question("presence_baseline", "Wozu dient die Notiz vor einem Übungsgespräch?",
                      ["Sie ermittelt die Gefühle der anderen Person", "Sie hält den eigenen Ausgangszustand fest", "Sie garantiert vollständige Neutralität"], 1),
            _question("presence_image", "Wie wird die Laterne in der Übung verwendet?",
                      ["Als persönliche freiwillige Vorstellung für Aufmerksamkeit", "Als nachgewiesener energetischer Schutz", "Als Pflichtübung für jedes Gespräch"], 0),
        ],
    },
    {
        "seed_key": "workspace_feldkonzept_v1",
        "week": 11,
        "title": "Das Feld als spirituelles Modell: bewusst einstimmen und offen bleiben",
        "category": "Intuition und Feldarbeit",
        "track": "Intuition und Feldarbeit",
        "level": "deepening",
        "summary": "Den Knowing-Field-Begriff kennenlernen und eine eigene symbolische Einstimmung gestalten, die innere Bilder, Kontakt und tatsächliche Rückmeldung unterscheidet.",
        "learning_objective": "Du kannst die Feldvorstellung als spirituelles Modell einordnen und eine selbst gewählte Einstimmung beschreiben, ohne daraus Wissen über eine entfernte Person abzuleiten. Vorwissen: eigener Ausgangszustand.",
        "body": _text("""
            Mark Jones nennt im öffentlichen Interview ein „Knowing Field“ und beschreibt
            es auch für Gespräche über Distanz. Das ist seine spirituelle Selbstaussage;
            das Interview liefert keinen Fernwahrnehmungsbeweis. Für unser Lernen ist
            interessant, welche Haltung ein solches Bild anregen kann: aufmerksam sein,
            nicht sofort alles erklären wollen und dem tatsächlichen Gespräch Platz
            lassen. Diese eigene praktische Übersetzung ist keine Methode von Jones.

            Das Wort Feld kann Unterschiedliches meinen. Jemand beschreibt damit ein
            spirituelles Verbundensein, jemand anderes die erlebte Atmosphäre eines
            Gesprächs. In Physik und anderen Wissenschaften hat es wiederum fachlich
            definierte Bedeutungen. Kläre daher zuerst, wie du das Wort verwendest.
            Eine geteilte Metapher kann eine Begegnung gestalten, ohne damit eine
            messbare Übertragung von Gedanken oder Gefühlen zu behaupten.

            Unsere eigene Einstimmung arbeitet mit dem Bild eines offenen Kreises.
            Du stellst dir zwei Plätze vor, auf denen beide Personen mit ihren
            unterschiedlichen Erfahrungen sitzen dürfen. Zwischen ihnen bleibt freier
            Raum für das, was erst ausgesprochen werden muss. Du musst diesen Raum
            nicht mit Eindrücken füllen. Auch ein gewöhnliches Gespräch ohne Bilder
            ist vollständig. Das Symbol soll Neugier und Gleichwertigkeit erinnern.

            In einem erfundenen Übungsgespräch taucht bei der Beraterin das Bild eines
            verschlossenen Fensters auf. Sie hält zunächst nur fest: „In meiner
            Vorstellung erscheint ein Fenster.“ Sie könnte das Bild für ihre eigene
            Aufmerksamkeit nutzen und sich fragen, ob sie gerade genug Raum lässt.
            Erst mit Zustimmung wäre es eine mögliche Einladung zur Reflexion. Es
            verrät weder, was die andere Person fühlt, noch welches Ereignis in
            ihrem Leben stattgefunden hat.

            Eine spirituelle Praxis darf auch still und unspektakulär bleiben. Vielleicht
            merkst du nur, dass du langsamer fragst. Vielleicht erlebst du nichts
            Besonderes. Notiere beides gleich sorgfältig. Der Wert dieser Übung liegt
            in einer bewussten Haltung und einer klaren Sprache für dein eigenes
            Erleben. Ob sich das Gegenüber gesehen oder unterstützt fühlt, kann nur
            dessen eigene Rückmeldung zum konkreten Gespräch zeigen.
        """),
        "exercise": _text("""
            Übe zuerst allein mit einer erfundenen Begegnung. Notiere deinen Ausgangszustand
            und wähle eine Absicht, etwa „Ich möchte eine Frage wirklich aussprechen
            lassen“. Stell dir für zwei Minuten den offenen Kreis vor oder zeichne
            zwei Plätze mit freier Mitte. Benenne alles Auftauchende als eigenes Bild,
            eigenen Gedanken oder eigene Empfindung. Formuliere danach eine neutrale
            Gesprächseröffnung und eine mögliche Einladung, ein Bild gemeinsam zu
            betrachten. Beende die Vorstellung, indem du die Zeichnung zusammenfaltest
            und drei Dinge im wirklichen Raum benennst. Wenn du später mit einer
            freiwilligen Übungspartnerin arbeitest, vereinbare diese Praxis ausdrücklich
            vorher und frage anschließend nach ihrer Erfahrung des Gesprächs.
        """),
        "reflection_prompt": "Was hat der offene Kreis an deiner Aufmerksamkeit verändert? Welche Beobachtung gehört eindeutig zu deinem eigenen Erleben, und welche Information könntest du erst durch eine ausdrückliche Rückmeldung erhalten?",
        "content_version": 1,
        "source_url": JONES_INTERVIEW,
        "source_title": "Mark Jones: The Therapeutic Potential of Astrology",
        "source_note": "Quelle belegt: Mark Jones: The Therapeutic Potential of Astrology (" + JONES_INTERVIEW + ") dokumentiert die Selbstaussage zum Knowing Field, auch über Distanz; kein Fernwahrnehmungsbeweis. Offener Kreis, Fensterbild, Gesprächsübersetzung, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Interview 2015/Website 2018, Prüfstand 20.10.2026. Kein Endorsement oder Nachbau eines Kurses.",
        "quiz": [
            _question("field_evidence", "Was belegt das Interview über das Knowing Field?",
                      ["Die zuverlässige Übertragung fremder Gefühle", "Eine spirituelle Selbstaussage von Mark Jones", "Eine kontrollierte Fernwahrnehmungsstudie"], 1),
            _question("field_image", "Ein inneres Fensterbild taucht auf. Was ist zunächst bekannt?",
                      ["Die andere Person verschweigt sicher etwas", "Ein tatsächliches Fenster im entfernten Raum ist geschlossen", "Du erlebst bei dir ein inneres Bild"], 2),
        ],
    },
    {
        "seed_key": "workspace_intuition_deutung_v1",
        "week": 12,
        "title": "Intuition und Deutung: ein Bild empfangen, ohne es festzuschreiben",
        "category": "Intuition und Feldarbeit",
        "track": "Intuition und Feldarbeit",
        "level": "deepening",
        "summary": "Mit einem spontan auftauchenden Bild arbeiten und zwischen eigener Empfindung, persönlicher Assoziation, astrologischer Lesart und fremder Rückmeldung unterscheiden.",
        "learning_objective": "Du beschreibst einen Eindruck zunächst ohne Herkunftsbehauptung und entwickelst mehrere mögliche Bedeutungen. Vorwissen: Feldkonzept als Modell und eine kurze Präsenzpraxis.",
        "body": _text("""
            Ein Eindruck kann schneller auftauchen als eine Erklärung: ein Wort, eine
            Farbe, eine Erinnerung oder eine Empfindung. Wir verwenden Intuition hier
            als Arbeitswort für solches unmittelbares persönliches Erleben. Dass etwas
            spontan erscheint, sagt noch nicht, woher es stammt oder ob eine spätere
            Deutung zutrifft. Du darfst den Eindruck ernst nehmen und seine Bedeutung
            trotzdem offenlassen. Offenheit kann genauer sein als Gewissheit.

            Unsere eigene Lernhilfe besteht aus vier getrennten Sätzen. Zuerst:
            „Ich bemerke …“ Dann: „Ich verbinde damit …“ Danach: „Eine mögliche
            symbolische Lesart wäre …“ Zuletzt: „Die andere Person sagt dazu …“
            Der letzte Satz bleibt leer, solange es keine tatsächliche Rückmeldung
            gibt. Eine vorgestellte Antwort gehört weiterhin zu deinen Assoziationen.
            Für das Üben brauchst du keine besondere Begabung nachzuweisen.

            Stell dir vor, dir kommt bei der Vorbereitung das Bild einer Holzbrücke.
            Die unmittelbare Beobachtung ist nur das innere Bild. Deine Assoziation
            könnte ein Übergang sein, aber ebenso ein vertrauter Spaziergang oder
            eine wackelige Konstruktion. Wenn du astrologisch mit Saturn arbeitest,
            kannst du nach tragfähiger Struktur fragen; mit Merkur eher nach
            Verständigung. Du hast damit verschiedene Deutungsangebote geschaffen,
            noch nichts über eine andere Person erfahren.

            Eine sorgfältige Einladung wäre: „Mir kam ein Brückenbild. Möchtest du
            es als Bild betrachten, oder bleiben wir lieber bei deinem Anliegen?“
            Wenn die Person zustimmt, kannst du fragen, ob und wie es für sie eine
            Bedeutung hat. Vielleicht denkt sie an Zusammenarbeit. Vielleicht findet
            sie das Bild unpassend. Beide Antworten lassen sich vollständig stehen
            lassen. Du brauchst das Bild nicht durch weitere Vorschläge zu retten.

            In deiner persönlichen spirituellen Praxis kannst du ein Bild zeichnen,
            ihm einen Platz im Journal geben und später mit Abstand zurückkehren.
            Gerade der Zeitabstand zeigt manchmal, wie stark die eigene Tagesstimmung
            beteiligt war. Mark Jones’ freie Videoübersicht ist ein möglicher Weg,
            verschiedene öffentliche Impulse selbst kennenzulernen. Sie ist keine
            Quelle für unsere Vier-Satz-Übung; diese wurde für SoulFlow entwickelt.
        """),
        "exercise": _text("""
            Betrachte für eine Minute einen gewöhnlichen Gegenstand, etwa einen Schlüssel
            oder eine Tasse. Wende den Blick ab und notiere, welches Bild oder Wort
            von selbst nachklingt. Fülle die ersten drei Sätze der Lernhilfe aus und
            entwickle drei voneinander verschiedene Bedeutungen. Lass das Rückmeldungsfeld
            leer. Wähle eine Bedeutung nur für deine eigene Reflexion und zeichne dazu
            eine kleine Szene. Kehre am nächsten Tag zurück: Welche Assoziation passt
            zu deinem damaligen Alltag? Falls du die Übung gemeinsam besprichst, bitte
            zuerst um Zustimmung und schreibe die Antwort möglichst genau auf. Vermische
            sie nicht mit dem, was du gern gehört hättest.
        """),
        "reflection_prompt": "Wie verändert sich dein Verhältnis zu einem Eindruck, wenn mehrere Bedeutungen nebeneinander möglich sind? Welche deiner Notizen ist Beobachtung, welche Assoziation, welche Deutung und welche tatsächliche Rückmeldung?",
        "content_version": 1,
        "source_url": JONES_VIDEOS,
        "source_title": "Mark Jones: Free Mark Jones Videos",
        "source_note": "Quelle belegt: Mark Jones: Free Mark Jones Videos (" + JONES_VIDEOS + ") bietet öffentliche Videozugänge als weiterführenden Originaleinstieg. Die Übersicht ist kein Volltextnachweis einzelner Videoaussagen. Vier-Satz-Lernhilfe, Brückenbild, Beispiel und Übung: eigene Redaktion, keine wiedergegebene Lehrmethode von Jones. Öffentliche englische Quelle, Prüfstand 20.10.2026.",
        "quiz": [
            _question("intuition_origin", "Was weißt du zunächst über ein plötzliches inneres Bild?",
                      ["Es ist eine eigene Wahrnehmung; seine Herkunft und Bedeutung sind offen", "Es enthält sicher eine fremde Erinnerung", "Spontaneität beweist eine übernatürliche Quelle"], 0),
            _question("intuition_columns", "Wann darf das Feld für die Rückmeldung ausgefüllt werden?",
                      ["Wenn du die wahrscheinlichste Antwort kennst", "Nach einer tatsächlichen Antwort der betreffenden Person", "Sobald die Symboldeutung überzeugend wirkt"], 1),
        ],
    },
    {
        "seed_key": "workspace_rueckmeldung_grenzen_v1",
        "week": 13,
        "title": "Rückmeldung und Grenzen: ein Nein aufnehmen und gut abschließen",
        "category": "Gespräch und Reflexion",
        "track": "Gespräch und Grenzen",
        "level": "deepening",
        "summary": "Mit Zustimmung, Widerspruch und Unklarheit praktisch umgehen und einen einfachen Abschluss mit einem selbst gewählten nächsten Schritt gestalten.",
        "learning_objective": "Du kannst eine unpassende Deutung zurücknehmen und einen Abschluss formulieren, der Anliegen, Eigenentscheidung und deine Angebotsgrenze sichtbar hält. Vorwissen: Eindruck und Deutung unterscheiden.",
        "body": _text("""
            Ein Gespräch wird nicht dadurch tief, dass jede Deutung Zustimmung erhält.
            Tiefe kann entstehen, wenn ein Gegenüber etwas präzisieren oder ablehnen
            darf. Mark Jones spricht im öffentlichen Interview über die Wirkung
            astrologischer Aussagen auf Ratsuchende. Unsere eigene Praxisaufgabe setzt
            deshalb beim Antwortverhalten an: Was machst du, nachdem eine Person
            sagt, dass dein Eindruck nicht passt?

            In unserem erfundenen Fall deutet eine Beraterin ein Bild als Wunsch nach
            Rückzug. Das Gegenüber antwortet: „Nein, ich möchte gerade unter Menschen.“
            Eine hilfreiche Reaktion lautet: „Dann verwerfe ich meine Rückzugsdeutung.
            Was wäre für dich eine gute Art von Gesellschaft?“ Die Beraterin muss
            das ursprüngliche Bild nicht umdeuten, bis es doch noch passt. Das Nein
            ist eine vollständige Rückmeldung und kein versteckter Widerstand.

            Auch ein Ja braucht Genauigkeit. „Das trifft irgendwie zu“ ist etwas
            anderes als ein selbst gewähltes, konkretes Beispiel. Frage ruhig nach,
            welcher Teil passend war und welcher nicht. Vermeide dabei, der Person
            bereits mehrere Geschichten anzubieten. Wenn sie unsicher bleibt, halte
            Unklarheit fest. Dein Journal soll die Antwort erhalten, nicht aus
            Höflichkeit eine erfolgreiche Deutung herstellen.

            Für einen eigenen Abschluss kannst du das Bild einer Schale verwenden.
            Lege gedanklich hinein, was heute tatsächlich besprochen wurde: eine
            Frage, eine hilfreiche Formulierung, einen offenen Punkt. Alles Ungeklärte
            muss nicht vor dem Ende gelöst werden. Bitte die Person, selbst einen
            Satz mitzunehmen. Du kannst dein eigenes inneres Bild anschließend
            ablegen, etwa durch eine geschlossene Notiz oder einen bewussten Blick
            aus dem Fenster. Dieses Ritual ist freiwillige persönliche Praxis.

            Grenzen werden konkret, wenn ein Anliegen deinen Rahmen übersteigt. Du
            kannst freundlich sagen, was du anbietest: spirituelle Reflexion und
            Gespräch im vereinbarten Umfang. Bei Fragen zu Diagnose oder Behandlung
            brauchst du keine astrologische Ersatzantwort. Bei eigener Überforderung
            darfst du unterbrechen. Ein guter Abschluss hinterlässt eine erkennbare
            Vereinbarung, keine Abhängigkeit von einer nächsten Deutung. Auch ein
            bewusst beendetes Thema kann ein stimmiges Ergebnis sein.
        """),
        "exercise": _text("""
            Schreibe drei kurze Gesprächsantworten auf: „Das passt“, „Das passt nicht“
            und „Ich weiß es nicht“. Antworte auf jede mit höchstens zwei Sätzen.
            In der zweiten Antwort nimmst du deine Deutung ausdrücklich zurück; in
            der dritten lässt du die Frage offen. Spiele die Szene laut durch und
            höre darauf, ob du um Zustimmung wirbst. Entwirf danach einen Abschluss
            von drei Minuten: Gesagtes zusammenfassen, einen selbst gewählten Satz
            mitnehmen lassen, offenen Punkt benennen und das Ende bestätigen. Nutze
            dabei auf Wunsch die Schale als inneres Bild. Notiere abschließend eine
            Formulierung, mit der du ein Anliegen außerhalb deines Angebots freundlich
            begrenzen kannst, ohne eine fachliche Lösung vorzutäuschen.
        """),
        "reflection_prompt": "Bei welcher Antwort wolltest du deine Deutung verteidigen? Welche Formulierung hat dir geholfen, Rückmeldung stehenzulassen und trotzdem einen zugewandten, klaren Gesprächsabschluss zu gestalten?",
        "content_version": 1,
        "source_url": JONES_INTERVIEW,
        "source_title": "Mark Jones: The Therapeutic Potential of Astrology",
        "source_note": "Quelle belegt: Mark Jones: The Therapeutic Potential of Astrology (" + JONES_INTERVIEW + ") thematisiert die mögliche Wirkung von Deutungsaussagen auf Ratsuchende. Antwortdialoge, Schalenbild, Begrenzungssätze, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Interview 2015/Website 2018, Prüfstand 20.10.2026. Kein Therapieverfahren und keine Übernahme bezahlten Unterrichts.",
        "quiz": [
            _question("feedback_no", "Die Person lehnt deine Deutung ab. Welche Reaktion passt?",
                      ["Das Nein als verborgene Bestätigung erklären", "Die Deutung verwerfen und beim ausgesprochenen Anliegen weiterfragen", "Weitere Geschichten anbieten, bis eine bestätigt wird"], 1),
            _question("feedback_unclear", "Wie dokumentierst du eine unklare Rückmeldung?",
                      ["Als Unklarheit mit der tatsächlichen Formulierung", "Als Treffer, wenn das Bild eindrucksvoll war", "Gar nicht, weil nur bestätigte Deutungen zählen"], 0),
        ],
    },
    {
        "seed_key": "workspace_telefon_ferne_v1",
        "week": 14,
        "title": "Telefon und Distanz: einen vereinbarten spirituellen Gesprächsraum öffnen",
        "category": "Praxis und Übung",
        "track": "Telefon- und Fernberatung",
        "level": "practice",
        "summary": "Einen kurzen Probetermin mit Anliegen, Zustimmung, optionaler Einstimmung, offenem Gespräch und bewusstem Abschluss strukturieren.",
        "learning_objective": "Du kannst eine freiwillige Übung am Telefon eröffnen, bei Änderungen erneut Zustimmung einholen und einen technischen Abbruch vorher vereinbaren. Vorwissen: Präsenz, Eindruck/Deutung und Rückmeldung.",
        "body": _text("""
            Ein Telefontermin kann persönlich und spirituell erlebt werden, obwohl
            beide Menschen an verschiedenen Orten sitzen. Das gemeinsame Gespräch
            entsteht durch vereinbarte Zeit, Aufmerksamkeit und Austausch. Jones’
            Interview enthält dazu seine Feldvorstellung; es belegt keine Übertragung
            fremder Gefühle. Der folgende Ablauf ist eine eigene SoulFlow-Übungsstruktur,
            keine Methode eines Lehrenden und kein Test paranormaler Fähigkeiten.

            Unser erfundener Fall ist ein Probetermin zwischen einer Beraterin in
            Deutschland und einer freiwilligen Übungspartnerin in Indien. Die Entfernung
            macht keine Annahme über Weltbild, Kultur oder Bedürfnisse erforderlich.
            Beide klären zuerst die vereinbarte Uhrzeit mit Zeitzonen, die Dauer,
            verständliche Sprache und ob sie gerade ungestört sprechen können. Die
            Übungspartnerin wählt ein gewöhnliches Anliegen, etwa Raum für ein kreatives
            Vorhaben zu finden. Es werden keine fremden Geburtsdaten benötigt.

            Die Beraterin beschreibt dann konkret, was sie vorschlägt: ein kurzes
            Ankommen, ein Gespräch und auf Wunsch die Arbeit mit einem Symbolbild.
            Sie fragt: „Möchtest du das ausprobieren?“ Eine Zustimmung zum Gespräch
            ist nicht automatisch Zustimmung zu jeder späteren Übung. Beide dürfen
            eine Pause, einen Themenwechsel oder ein Ende wünschen. Eine Aufzeichnung
            gehört nicht zu dieser Übung; sie bräuchte eine eigene ausdrückliche
            Vereinbarung.

            Für die freiwillige Einstimmung kann jede Person einen Gegenstand in
            ihrem eigenen Raum wählen. Ein Stein, eine Tasse oder ein Blatt erinnert
            an die persönliche Absicht. Nach einer stillen Minute benennt jede
            nur die eigene Erfahrung. Anschließend stellt die Beraterin eine offene
            Frage zum Anliegen. Taucht ein Bild auf, bietet sie es zuerst zur
            freiwilligen Betrachtung an, statt daraus einen Zustand des Gegenübers
            abzuleiten. Stille am Telefon darf durch eine einfache Rückfrage geklärt
            werden; sie hat nicht von selbst eine spirituelle Bedeutung.

            Zum Abschluss fasst die Übungspartnerin selbst zusammen, was hilfreich
            war. Beide legen den Gegenstand bewusst zurück und bestätigen das Ende.
            Falls die Verbindung abbricht, gilt die vorherige Absprache, etwa ein
            einmaliger erneuter Anruf und danach Ende des Termins. So bleibt der
            Rahmen auch dann verständlich, wenn die Technik den Gesprächsfluss
            unterbricht.
        """),
        "exercise": _text("""
            Entwirf einen Probetermin von fünfzehn Minuten: drei Minuten für Vereinbarung
            und Anliegen, zwei für freiwilliges Ankommen, sieben für das Gespräch und
            drei für Rückmeldung und Abschluss. Schreibe deine Einladungsfrage und die
            Absprache bei Verbindungsabbruch aus. Übe den Ablauf zuerst allein laut.
            Für einen tatsächlichen Probetermin brauchst du eine freiwillige erwachsene
            Übungspartnerin, die den Lerncharakter kennt. Lass sie zwischen stillem
            Ankommen und direktem Gespräch wählen. Notiere nachher nur anonymisiert,
            was du angeboten hast, wozu sie zugestimmt hat und wie der Abschluss
            verlief. Bewerte die Klarheit des Rahmens, nicht eine vermeintliche Fähigkeit,
            über Entfernung etwas zu fühlen.
        """),
        "reflection_prompt": "War die Zustimmung zu jedem angebotenen Schritt verständlich? Wo hast du am Telefon etwas angenommen, das sich mit einer einfachen Rückfrage klären ließ, und wie hat der Abschluss gewirkt?",
        "content_version": 1,
        "source_url": JONES_INTERVIEW,
        "source_title": "Mark Jones: The Therapeutic Potential of Astrology",
        "source_note": "Quelle belegt: Mark Jones: The Therapeutic Potential of Astrology (" + JONES_INTERVIEW + ") beschreibt ein Feld auch im Distanzgespräch als Selbstaussage. Terminstruktur, Zustimmungsfragen, Gegenstandsritual, Beispiel und Übung: eigene Redaktion. Öffentliche englische Quelle, Interview 2015/Website 2018, Prüfstand 20.10.2026; kein Fernwahrnehmungsbeweis oder Lehrer-Endorsement.",
        "quiz": [
            _question("phone_consent", "Nach Gesprächsbeginn möchtest du eine Bildübung anbieten. Was ist erforderlich?",
                      ["Eine erneute konkrete Zustimmung zur angebotenen Übung", "Nur die ursprüngliche Terminbuchung", "Eine Vermutung, dass die Person spirituell offen ist"], 0),
            _question("phone_silence", "Was bedeutet eine längere Stille am Telefon zunächst?",
                      ["Sicher eine tiefe energetische Wirkung", "Sie ist mehrdeutig; eine Rückfrage kann den Zustand des Gesprächs klären", "Die Person stimmt jeder Deutung zu"], 1),
        ],
    },
    {
        "seed_key": "workspace_uebungsjournal_v1",
        "week": 15,
        "title": "Das Übungsjournal: Erfahrung, Rückmeldung und nächsten Schritt bewahren",
        "category": "Praxis und Übung",
        "track": "Praxis aufbauen",
        "level": "practice",
        "summary": "Eine persönliche Journalvorlage für Lesen, Üben und Reflektieren entwickeln und drei kleine Übungsszenen ohne Trefferstatistik auswerten.",
        "learning_objective": "Du führst eine nachvollziehbare anonyme Lernnotiz mit Quellen- und Versionsbezug und leitest daraus eine konkrete Verbesserung ab. Vorwissen: Empfindung, Deutung und Rückmeldung unterscheiden.",
        "body": _text("""
            Ein gutes Übungsjournal bewahrt, was geschehen ist, bevor die Erinnerung
            daraus eine glatte Geschichte macht. Es darf persönlich, bildhaft und
            spirituell sein. Zugleich hilft eine einfache Struktur, verschiedene Arten
            von Einträgen auseinanderzuhalten. Gelesen bedeutet, dass du einen Text
            aufgenommen hast. Geübt bedeutet, dass du etwas ausprobiert hast.
            Reflektiert bedeutet, dass du den Versuch mit Abstand betrachtet hast.
            Keine dieser Markierungen ersetzt die andere.

            Die öffentliche Ausbildungsseite von Silke Schäfer unterscheidet Grundlagen
            und weiterführende Lernabschnitte und verbindet Lernen mit eigener Erfahrung.
            Wir übernehmen daraus nur die Anregung einer gegliederten Lernstruktur.
            Unsere Journalvorlage ist eigene Redaktion, keine Abschrift von Kursmaterial
            und kein Ersatz für eine Ausbildung. Du kannst mit einem einzelnen
            Thema beginnen und deinen nächsten Schritt selbst wählen.

            Für unsere Vorlage genügen sechs kleine Felder: Anlass, eigener
            Ausgangszustand, beobachteter Eindruck, mögliche Lesart, tatsächliche
            Rückmeldung und nächster Versuch. Ergänze Lektionstitel und Inhaltsversion,
            wenn eine Notiz aus einem Kapitel entsteht. Bei einer selbst gewählten
            Praxis kannst du ein persönliches Symbol dazusetzen. Ein gezeichnetes
            Blatt könnte etwa daran erinnern, einen Gedanken erst wachsen zu lassen,
            bevor du ihn aussprichst.

            Unser erfundener Eintrag handelt von einer Übung zum Zuhören. Vorher war
            die Beraterin ungeduldig. Währenddessen tauchte das Wort „Aufbruch“ auf.
            Ihre Lesart war ein Wunsch nach Veränderung. Die Übungspartnerin sagte
            jedoch, sie wünsche sich gerade einen verlässlichen Rhythmus. Der nächste
            Versuch lautet deshalb: zuerst nach dem aktuellen Anliegen fragen und
            das innere Wort nur für die eigene Reflexion nutzen. Der Eintrag ist
            nützlich, obwohl keine Deutung bestätigt wurde.

            Schaue nach mehreren Einträgen nach deinen Arbeitsmustern. Hast du häufig
            vor der ersten Frage schon eine Geschichte? Enden die Gespräche klar?
            Wo bleibt Zustimmung unklar dokumentiert? Das sind auswertbare Lernfragen.
            Drei bestätigende Antworten ergeben keine verlässliche Hellsichtigkeitsquote;
            dafür fehlen kontrollierte Bedingungen und eindeutige Vergleichskriterien.
            Für deinen Lernfortschritt ist ohnehin hilfreicher, welche Verhaltensweise
            du bewusst ändern kannst. Bewahre fremde personenbezogene Angaben nicht
            in einer Lernnotiz auf; anonyme Szenen reichen dafür aus.
        """),
        "exercise": _text("""
            Erstelle im privaten Notizbuch einen Eintrag mit den sechs Feldern. Fülle
            ihn zuerst mit dem erfundenen Aufbruch-Beispiel und kennzeichne ihn als
            synthetische Übung. Lege danach zwei weitere kurze Einträge aus eigenen
            Alltagssituationen an, etwa einem kreativen Versuch oder einer Übung allein.
            Lass Rückmeldung leer, wenn niemand tatsächlich geantwortet hat. Markiere
            getrennt, ob du gelesen, geübt oder reflektiert hast. Vergleiche die drei
            Einträge am nächsten Tag und wähle genau eine veränderbare Arbeitsweise,
            zum Beispiel vor jedem Deutungsvorschlag eine offene Frage zu stellen.
            Schreibe dazu einen konkreten nächsten Versuch und wann du ihn betrachten
            möchtest. Persönliche Symbole dürfen die Struktur ergänzen.
        """),
        "reflection_prompt": "Welche Beobachtung über deine Arbeitsweise wird erst durch mehrere Einträge sichtbar? Was möchtest du beim nächsten Versuch anders tun, und woran würdest du diese Veränderung tatsächlich erkennen?",
        "content_version": 1,
        "source_url": SCHAEFER_CURRICULUM,
        "source_title": "Silke Schäfer: Grundausbildung",
        "source_note": "Quelle belegt: Silke Schäfer: Grundausbildung (" + SCHAEFER_CURRICULUM + ") zeigt eine gegliederte öffentliche Ausbildungsstruktur. Nur diese Struktur dient als Bezug, keine bezahlten Kursinhalte. Journalvorlage, Blattsymbol, Aufbruch-Beispiel und Übung: eigene Redaktion. Öffentliche deutsche Angebots-/Curriculumseite, Prüfstand 20.10.2026; keine Kooperation oder Qualifikationszusage.",
        "quiz": [
            _question("journal_proof", "Welche paranormale Fähigkeit belegen drei zustimmende Rückmeldungen im Journal?",
                      ["Zuverlässige Fernwahrnehmung", "Keine; dafür sind diese Übungsnotizen kein geeigneter Nachweis", "Vollständige Kenntnis fremder Gefühle"], 1),
            _question("journal_states", "Welche Aussage beschreibt die drei Lernzustände passend?",
                      ["Gelesen, geübt und reflektiert beschreiben verschiedene Tätigkeiten", "Gelesen bedeutet automatisch praktisch geübt", "Ein Quiz ersetzt jede praktische Reflexion"], 0),
        ],
    },
    {
        "seed_key": "workspace_quellenlernen_v1",
        "week": 16,
        "title": "Mit Originalquellen lernen: Lehrtraditionen vergleichen und selbst weiterdenken",
        "category": "Praxis und Übung",
        "track": "Quellenlernen",
        "level": "practice",
        "summary": "Öffentliche Originale gezielt auswählen, ihre Quellenrolle benennen und eine eigene Lernfrage entwickeln, ohne fremde Kurse zu kopieren.",
        "learning_objective": "Du erstellst eine kleine Quellenkarte, trennst belegte Aussage von eigener Schlussfolgerung und entscheidest über einen nächsten Lernschritt. Vorkenntnisse sind nicht erforderlich; englische Originale sind entsprechend gekennzeichnet.",
        "body": _text("""
            Eine Bibliothek wird erst durch deine Fragen zu einem Lernraum. Du musst
            nicht jeden Beitrag ansehen und auch keinem Lehrenden vollständig folgen.
            Beginne mit einer überschaubaren Frage, etwa: Wie möchte ich ein
            astrologisches Symbol in einem Gespräch verwenden? Wähle dafür ein
            öffentlich zugängliches Original, das du tatsächlich lesen oder ansehen
            kannst. Ein Titel oder Suchtreffer allein ersetzt noch keine Inhaltsprüfung.

            Die öffentliche Grundausbildungsseite von Silke Schäfer zeigt eine deutsche
            Lernstruktur. Mark Jones stellt auf seiner Website eine englische Übersicht
            freier Videos bereit. Diese Quellen haben unterschiedliche Rollen: ein
            Curriculum beschreibt einen Lernweg, ein selbst angesehenes Video kann
            eine konkrete Aussage enthalten. Beides wird durch unsere Verlinkung
            weder eine geprüfte Ausbildung noch eine Empfehlung aller angebotenen
            Inhalte. Die Schulen bleiben voneinander unterscheidbar.

            Unsere eigene Quellenkarte hat fünf Zeilen: Autor und Titel, genauer
            Link, Datum deines Zugriffs, tatsächlich bearbeiteter Abschnitt und
            Quellenrolle. Ergänze danach zwei deutlich getrennte Felder: Was sagt
            die Quelle? Was denke oder erprobe ich selbst? Für deine erste
            Zusammenfassung reichen wenige eigene Sätze. Notiere beim Video eine
            Zeitstelle, beim Text eine Abschnittsüberschrift. Wenn du eine Aussage
            nicht sicher verstehst, lass sie als offene Frage stehen.

            Im erfundenen Beispiel vergleicht eine Lernende zwei Zugänge zum
            gleichen Bild eines Weges. In ihrer eigenen ersten Lesart steht er
            für Entwicklung, in der zweiten für eine alltägliche Entscheidung.
            Sie hält fest, welche Bedeutung sie selbst hinzugefügt hat. Danach
            fragt sie: Welche Perspektive hilft mir, eine konkrete Frage zu
            stellen? Sie muss unterschiedliche spirituelle Annahmen nicht zu einem
            einzigen System verschmelzen, um von beiden angeregt zu werden.

            Öffentliche Zugänglichkeit ist keine allgemeine Erlaubnis, Unterricht
            zu kopieren. Für dein Journal sind kurze eigene Einordnungen, Links
            und selbst entwickelte Übungen der passende Ausgangspunkt. SoulFlow
            aktualisiert diese Quellen nicht automatisch. Prüfe Datum und Zugang,
            wenn du sie später wieder aufrufst. Ein Buchzeichen bewahrt deinen
            Einstieg; eine Versionsnotiz bewahrt, auf welchen Lerntext du dich
            bezogen hast. So kann sich deine Sicht verändern, ohne dass frühere
            Notizen ihre Herkunft verlieren.
        """),
        "exercise": _text("""
            Öffne die verlinkte deutsche Curriculumseite und notiere ausschließlich,
            welche Lernstruktur du dort selbst erkennen kannst. Wähle danach auf
            Wunsch einen öffentlich zugänglichen englischen Videoeinstieg von Mark
            Jones, ohne etwas zu kaufen. Wenn Sprache oder Zugang nicht passen,
            halte genau diese Grenze fest und bleibe bei einer verfügbaren Quelle.
            Erstelle eine Quellenkarte für den tatsächlich bearbeiteten Abschnitt.
            Schreibe drei eigene Sätze dazu: eine nachvollziehbare Quellenbeobachtung,
            eine persönliche Frage und eine selbst entwickelte kleine Übung. Notiere,
            was du noch nicht geprüft hast. Entscheide anschließend, ob du dieses
            Original vertiefen oder zunächst ein Grundlagenkapitel wiederholen möchtest.
            Ein einzelner gut verstandener Abschnitt genügt für diesen Versuch.
        """),
        "reflection_prompt": "Welche Aussage kannst du an einer konkreten Stelle der Quelle wiederfinden? Welche Idee stammt von dir selbst, und welche offene Frage bestimmt deinen nächsten freiwilligen Lernschritt?",
        "content_version": 1,
        "source_url": SCHAEFER_CURRICULUM,
        "source_title": "Silke Schäfer: Grundausbildung",
        "source_note": "Quelle belegt: Silke Schäfer: Grundausbildung (" + SCHAEFER_CURRICULUM + ") dokumentiert den deutschen öffentlichen Lernaufbau. Ergänzung: Mark Jones: Free Mark Jones Videos (" + JONES_VIDEOS + ") listet freie englische Videozugänge; einzelne Videos wurden für diese Lektion nicht inhaltlich ausgewertet. Quellenkarte, Wegbeispiel und Übung: eigene Redaktion. Prüfstand 20.10.2026; keine bezahlte Kurskopie, Kooperation oder automatische Aktualisierung.",
        "quiz": [
            _question("sources_roles", "Was sollte eine nützliche Quellenkarte zusätzlich zu Autor und Link enthalten?",
                      ["Eine erfundene Qualifikation des Lehrenden", "Die Anzahl der Menschen, die vermutlich zustimmen", "Den bearbeiteten Abschnitt, Zugriffsdatum und Quellenrolle"], 2),
            _question("sources_unread", "Was belegt eine freie Videoübersicht ohne angesehenes Video?",
                      ["Dass dort Videozugänge gelistet sind", "Alle Aussagen jedes Videos", "Die Wirksamkeit jeder darin angebotenen Methode"], 0),
            _question("sources_own", "Welche Weiterverarbeitung ist für die Übung vorgesehen?",
                      ["Eine vollständige Kursübersetzung ohne Erlaubnis", "Kurze eigene Einordnung, Originalverweis und selbst entwickelte Übung", "Quellenangaben entfernen, damit alles einheitlich wirkt"], 1),
        ],
    },
)
