import csv
import argparse
import os

# 📂 Définir le chemin absolu du fichier CSV
CSV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datas", "curateurs.csv"))

# 📁 Créer le dossier cible s'il n'existe pas
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)


def creer_csv(noms: list):
    """Crée un nouveau fichier CSV avec la liste des noms (triés et sans doublons)."""
    with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["nom"])
        for nom in sorted(set(noms)):
            writer.writerow([nom])
    print(f"✅ Fichier créé: {CSV_PATH}")


def ajouter_curateurs(noms: list):
    """Ajoute de nouveaux noms dans le fichier CSV sans doublons."""
    existants = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existants.add(row['nom'])

    total = existants.union(noms)

    with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["nom"])
        for nom in sorted(total):
            writer.writerow([nom])
    print(f"✅ Ajout(s) terminé(s), total: {len(total)} noms")


def supprimer_curateurs(noms: list):
    """Supprime des noms du fichier CSV."""
    if not os.path.exists(CSV_PATH):
        print("❌ Le fichier n'existe pas.")
        return

    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existants = set(row['nom'] for row in reader)

    total = existants - set(noms)

    with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["nom"])
        for nom in sorted(total):
            writer.writerow([nom])
    print(f"✅ Suppression terminée, restant: {len(total)} noms")


def parse_args():
    parser = argparse.ArgumentParser(description="Gestion du fichier des curateurs")
    parser.add_argument('--action', choices=['create', 'add', 'remove'], required=True, help="Action à effectuer")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # 🧾 Liste combinée des curateurs à gérer
    curateurs = [
        "GéVERS Raphaël", "CIARNIELLO Julien", "LE HARDŸ DE BEAULIEU Tibault", "OUCHINSKY Nicholas", "HENRI Jérôme",
        "STOOP Guillaume", "DESPONTIN Audrey", "PATERNOSTRE DE HAULLEVILLE Dimitri", "PHILIPPE Anne-Laure",
        "ALSHIQI Genc", "HENRI Jérôme", "CORNET D'ELZIUS DU CHENOY Christophe", "CLEVENBERGH Olivier",
        "DE WOLF Patrick",  "DE BONNET Julie", "MESSINNE Francine", "LANOTTE Adrien",
        "LHOIR Tristan", "DE RIDDER Julie", "TOSSENS Jean-François", "RATA Ruxandra", "CHARDON Christophe",
        "SPRINGUEL Charles-Henri", "VAN VEERDEGEM Alain", "GOOSSENAERTS Alexander", "VANLAETHEM Simon",
        "BIHAIN Luc", "CECCALDI Marion", "BONNET Laurence", "BEGHIN François", "OUCHINSKY Victor",
        "DUQUESNE WATELET DE LA VINELLE Bruno", "ROLAND Nicolas", "PIRARD Gautier", "STOOP Guillaume",
        "ENSCH Ysabelle", "BERMOND Lucille", "VAN DE VELDE Claire", "GJONI Mirjan", "THYS Emmanuel",
        "EL MAKAOUI EL KAFI Omar", "MATHY Frédérique", "HERTOGS Coralie", "DUBUFFET Marie-Françoise",
        "PARK Chan", "DEMBLON François", "CORRIERE Clio", "HOC Albert", "SIMON Hugues", "HEILPORN Lise",
        "LOHISSE David", "FORTEMPS Sandy", "BOON-FALLEUR Laurence", "HUART Sophie", "CORNEJO MONTERO Ximena",
        "GNAKOURI Moïse Achille", "CHAUDHARY Usman Ali", "CREPLET Olivier", "LOUIS Eric", "FONTAINE Anne",
        "VALVERDE BURGOS Hernan", "CHEF Hadrien", "BOUTON Guillaume", "BINDELLE Thierry", "BOURTEMBOURG Christophe",
        "DESPONTIN Audrey", "BAUM Anicet", "DE SCHAETZEN VAN BRIENEN Hugues", "DUMONT Guillaume",
        "CIARNIELLO Julien", "DE SAUVAGE Grégory", "HERINCKX Catherine", "DAL Georges-Albert", "DE FRANCQUEN Vanessa",
        "WILLOCX Quentin", "ELSE DALLE EBONGUE Catherine", "CUSAS Eric", "ALTINDAL Karbeyaz", "VAN ROOST Philippe",
        "OSSIEUR Diane", "HENDERICKX Alain A.", "GOFFART Melisande", "GOLDSCHMIDT Alain",
        "Yannick ALSTEENS", "Luc AUSTRAET", "Christophe BAUDOUX", "Anicet BAUM", "Lucille BERMOND",
        "Thierry BINDELLE", "Anthony BOCHON", "Emmanuelle BOUILLON", "Christophe BOURTEMBOURG",
        "Christophe CHARDON", "Georges-Albert DAL", "Philippe DECHAMPS", "Geneviève DEDOBBELEER",
        "Charles de la VALLEE POUSSIN", "Jean-Michel DERICK", "Frederik DE VULDER", "Alain D'IETEREN",
        "Charles DUMONT de CHASSART", "Ysabelle ENSCH", "Michel FONTIGNY", "Jean-Claude GOBLET",
        "Yves GODFROID", "Alain GOLDSCHMIDT", "Maïa GUTMANN le PAIGE", "Françoise HANSSENSENSCH",
        "Lise HEILPORN", "Alain HENDERICKX", "Jérôme HENRI", "Catherine HERINCKX", "Sophie HUART",
        "Guy KELDER", "Frédéric KERSTENNE", "François LE GENTIL de ROSMORDUC", "Luc LEMAIRE",
        "Pol MASSART", "Emilie MICHEL", "Yves OSCHINSKY", "Diane OSSIEUR", "Gauthier PIRARD",
        "Jacques PIRON", "Virginie SALTEUR", "Alexandre SAUSSEZ", "Guillaume SNEESSENS",
        "Charles-Henri SPRINGUEL", "Eyal STERN", "Guillaume STOOP", "Vincent TERLINDEN",
        "Emmanuel THYS", "Mélanie VALLES RUIZ", "Alain G.VANDAMME", "Nicolas VAN der BORGHT",
        "Claire VAN de VELDE", "Philippe VANDE VELDE MALBRANCHE", "Bernard VANHAM",
        "Jeanine WINDEY", "D'AOUT Olivier", "ROBIJNS Olivier", "HERVE Luc", "THUNUS Elodie", "PROUMEN Léon-Pierre",
        "CAUSIN Eric", "LEMMENS Sarah", "DOUNY Raphaël", "DEWANDRE Caroline", "ABSIL Adrien",
        "DERROITTE Jean-François", "KOTIDIS Constantin", "LEDAIN Frédéric", "CHARLIER Dominique",
        "JAMINET Jean-François", "FRANCK Edouard", "JACQUINET Barbara", "DELVENNE Julien",
        "DESSARD Damien", "BOURLET Pierre-François", "COURBE Sibylle", "STRUNZ Jan-Henning",
        "ESCHWEILER Olivier", "DOR Bruno", "TASSET Jean-Paul", "MOïSES François",
        "BIEMAR Isabelle", "BODEN François", "BAERTS Audrey", "REMICHE Charlotte", "BIHAIN Luc",
        "CLOSON Gilles", "NEURAY Julie", "STAS DE RICHELLE Laurent", "DEPREZ Michel",
        "LEJEUNE Albert-Dominique", "BOULANGÉ Pierre", "DESTREE Philippe", "KERSTENNE Frédéric",
        "MINON François", "IMFELD Guido", "EVRARD Olivier", "DELFORGE Murielle", "BISINELLA Yves",
        "MOTTARD Philippe", "CHEN Yuqin", "DOTRIMONT Chloé", "HANNON Anne-Michèle",
        "MARNETTE Ludovic", "WUIDARD Jean-Luc", "BORTOLOTTI Aurélien", "GODFROID Yves",
        "CAVENAILE Thierry", "LEVAUX Marc", "VON FRENCKELL Ingrid", "ERNOTTE Florian",
        "CHARLES Xavier", "MAQUET Bernard", "LAZAR Alexandru", "THIRY Pierre", "VIESLET Samuel",
        "GRIGNARD Didier", "RÉSIMONT Clément", "HUSSON Jean-Marc", "HANSSENS Sarah",
        "CORBEEL Thierry", "VAN ELEWYCK Guillaume", "DUBOIS Julien", "LITANNIE Thierry",
        "PHILIPPART Maureen", "DE JAMBLINNE Nicolas", "BRAUN Antoine", "LABONTE Marie-Aurore", "PHILIPPO Brieuc",
        "BASTENIèRE Jean-Noël", "HARDY Justine", "PIETTE Xavier", "FRANCK Christian", "VANHAM Bernard",
        "JACOBS Mathieu", "JANSSENS Olivier", "HEUGHEBAERT Pierre", "BERLIER Guillaume", "LANGE Amélie",
        "VAN ELDER Gaëtan", "WILLEZ Olivier", "VANHEMELEN Marie", "SEBAYOBE Olivia", "BASTIEN Stéphanie",
        "DE KEYZER Gabriel", "GLAUDE Bernard", "BOIGELOT Eric", "SPEIDEL Marc-Alain", "LEPLAT Gérard",
        "GOETHALS Luc", "SALTEUR Virginie", "DUMONT DE CHASSART Charles-Albert", "BARY Hugues", "HAVET Jérôme",
        "DEPOORTER Christophe", "WéRY Barbara", "BONOMINI Alessia", "STOOP Guillaume", "VAN GILS Xavier",
        "COSTANTINI Alain", "DARCHEVILLE Samuel", "COOLS-DOUMONT Annette", "CLAREMBAUX Michaël", "THOMAS Ségolène",
        "DELPLANCHE Julian", "CECCARINI Noa", "VANDENBOSSCHE Magali", "MOULINASSE Bruno", "WOUTERS Maxime",
        "GRéGOIRE Pierre", "IBARRONDO Xavier", "CIERO Melissa", "WOUTERS Nicolas", "DONéA Marie-Pierre",
        "DUDKIEWICZ Pauline", "CREA Théo", "DEGROS Lauriane", "CATFOLIS Damien", "DEBONNET Victor", "DEMETS Julie",
        "MERCIER Olivier-A", "CHANTRY Valentine", "GONDAT Marc Fernand J", "LAVENS Mathieu", "DUBART Camille",
        "GUSTIN Jean-Max", "PRINTZ Yves", "SION François", "COMBREXELLE Angélique", "HOC Benoît", "TELLIER Dominique",
        "DANCOT Véronique", "ELOY Gaëlle", "DALLAPICCOLA Jessica", "LENOIR Christophe", "DELFORGE Murielle",
        "LARBIERE Patrick", "CRISCENZO Paolo", "BAUDOUX Gentiane", "DAVREUX Jean-François", "LEBLANC Céline",
        "PROESMANS Jean", "CHANTRAINE David", "HANNEN David", "MEESSEN Matthias", "BODARWé Chantal",
        "BERNARD Laurent", "DELPÉRÉE Jean Francis", "ALAIME Baptistin", "DE CORDT Yves", "DE RIDDER Karl",
        "LEMAIRE Geoffroy", "DENÈVE Marc", "DELBRASSINNE Eric", "BRONKAERT Isabelle", "BORN Maxime",
        "DEWAIDE Xavier", "VAN MOPPES Dave", "RONCOLETTA Alexandre", "JAUMAIN John", "BRINGARD Francis",
        "BOSSARD Philippe", "LYAZOULI Karim", "CORNIL David", "GLAUDE Bernard", "GOSSIAUX Marie", "ADAM Marie",
        "DUSAUCY Vincent", "DEPREZ Jean-Pierre", "VAN DORPE Benjamin", "TINELLI Fiona", "BOURLET Guillaume",
        "CEOLA Fabrice", "BONGIORNO Sabrina", "CASTAIGNE Bernard", "VALANGE Olivier", "DUFOUR Denis",
        "SIMONART Philippe", "HENRI Jérôme", "BOERAEVE Christophe", "VAN BEVER Michaël", "MARESCHAL Olivier",
        "MIHUT Florin", "VON KUEGELGEN Manuela", "TAPI Dakouri Sylvain", "STOOP Guillaume", "WELSCH Anne",
        "DEBAUDRENGHIEN Nicolas", "ESAKWA AYIMONA Jennifer", "SAERENS Patrick", "TORO Jonathan", "PEREN Nicolas",
        "BRENEZ Elisabeth", "CHARLIER Cynthia", "NACHSEM Stéphanie", "GANHY Charlotte", "LAMBERT Dominique",
        "BOCHON Anthony", "BERMOND Lucille", "GRIESS Steve", "GERNAY Olivier", "LANGLOIS DE BAZILLAC Pierre",
        "LOOZE Mathias", "THYS Emmanuel", "RULKIN Guy", "DECKERS Vincent", "LAMBEAU Arthur", "KNOPS Gil",
        "TILQUIN Thierry", "VAN BOXSTAEL Catherine", "MALHERBE Cédric", "CAMINO-GARCIA Clara", "FERRANT Isabelle",
        "SIMON Hugues", "SARTINI-VANDENKERCKHOVE Christine", "VAN CROMBRUGGHE Nicole", "AUBERTIN Jérôme", "MORENO Paul",
        "LEBUTTE Michel", "ESKÉNAZI Stanislas", "BOUTEILLER Victor", "ALTINDAL Karbeyaz", "LEBLANC Victor",
        "CULOT Henri", "SCHOLLAERT Mélanie", "BARTHOLOMEEUSEN Alain", "HOOGSTOEL Tamara", "DEHON Philippe",
        "NAFTALI Jonathan", "PIETERAERENS Eddy", "HEILPORN Etienne", "CEYLAN Seyit Ali", "RENARD Jean Pierre",
        "VANDEN EYNDE Johan", "ALTER Cédric", "JOACHIMOWICZ Marcel", "LESCOT Virginie", "VAN BUGGENHOUT Maxim",
        "DAUBE Mélanie", "VOISIN Sylvie", "DELHAYE Dorian", "DELMARCELLE Christophe", "MARQUETTE Vanessa",
        "PONTEVILLE Laurent", "PHILIPPE Denis", "WARZÉE Fabian", "DECLÈVE Antoine", "ITANI Makram", "DELMOITIÉ Nicolas",
        "HENDLISZ Gilbert", "FORT Markus", "DEKEMEXHE Clément", "FORET Françoise", "DELACROIX Sebastien",
        "SCIAMANNA Anne-Catherine", "KOUEMBEU-TAGNE Jean-Jacques", "VAESEN Justine", "CLÉMENT Jérôme",
        "BAIVIER Jean", "FRÉDÉRICK François", "DORTHU Pierre", "PROPS Roland", "HANCHIR Sarah", "VOISIN Jules",
        "ZIANS Guido", "PARISI Massimiliano David S", "CHARLEZ François", "BRILLON Cédric", "CARION Guillaume",
        "DUSAUSOIT Pierre-Yves", "CABY Axel", "LEFÈBVRE Gauthier", "FRITZ Martin", "DEBETENCOURT Paul",
        "PERET Bertrand", "DEHANT Xavier", "FRANSSEN Christophe", "BAUDOUX Gentiane", "CASTAIGNE Bernard",
        "GUCHEZ Stéphane", "BRICHART Jean", "LEFÈVRE Christophe", "CANVAT Raphaël", "OGER Luc", "HUMBLET Bénédicte",
        "DE NÈVE Marie-Thérèse", "LEJEUNE Lionel", "D'HEUR Pierre", "LEDOUX Géraldine", "POCHET Samuel",
        "STUBLA Fatmir", "DANCOT Véronique", "BESSALAH Dalila", "PARADIS Xavier", "FAVART Pierre", "GHILAIN Mélanie",
        "SCHEERS Valérie", "BRULARD Yves", "GIUNTA Vincent", "DUSAUSOIT Pierre-Yves", "BRUX Stéphane",
        "VERBRUGGE Gaëtan", "MATERNE Jérôme", "VANGANSBERG Chloé", "VAN BEVER Michaël", "DEMOL David",  "DE CORDT Yves",
        "BOSSARD Philippe", "PERINI Grégory", "PIR Pelin", "DEMOL David", "ZUINEN Thierry", "BERTIEAUX Charlotte",
        "SCHREDER Philippe-Robert", "MALORGIO Marie", "CORNIL Pierre E.", "LAURENT Julien", "KRACK Louis",
        "DEPREZ Nicole", "LAMBOT Muriel", "GASPARD Daniel", "VIDAICH Stephane", "GHILAIN Mélanie", "HARDY Simon",
        "CHARLEZ François", "COLLIN Frédéric", "MASSART Olivier", "DELINTE Lisa", "LEMAIRE Pierre", "GUCHEZ Stéphane",
        "GROFILS Bernard", "BISINELLA Yves", "OUCHINSKY Nicholas", "BRULARD Yves", "STOOP Guillaume",
        "ALSTEENS Yannick", "HARDY Justine", "SEBAYOBE Olivia", "JANSSENS Olivier", "DE KEYZER Gabriel",
        "SALTEUR Virginie", "BASTIEN Stéphanie", "PHILIPPO Brieuc", "PIETTE Xavier", "DHEYGERE Eléonore",
        "COSTANTINI Alain", "MOëNS Philippe", "CHARDON Christophe", "CIERO Melissa", "GOETHALS Luc",
        "VANDENBOSSCHE Magali", "KARIOUN Soraya", "GLAUDE Bernard", "VAN GILS Xavier", "IBARRONDO Xavier",
        "VANHAM Bernard", "DARCHEVILLE Samuel", "LANGE Amélie", "DEDOBBELEER Geneviève", "LEPLAT Gérard",
        "BONOMINI Alessia", "WESTERLINCK Eléonore", "BASTENIèRE Jean-Noël", "DE SAN Rodolphe", "DELPLANCHE Julian",
        "STOOP Guillaume", "BRAUN Antoine", "MALSCHALCK Clémentine", "COOLS-DOUMONT Annette", "WOUTERS Maxime",
        "HELLEBAUT Hedwige", "HAVET Jérôme", "CLAREMBAUX Michaël", "BAUDOUX Christophe",
        "DUMONT DE CHASSART Charles-Albert", "SPEIDEL Marc-Alain"]

    administrateurs_provisoires = [
        "COLARDI Nathalie", "LEURQUIN Brigitte", "PERINI Grégory", "LEJOUR Anny", "L'HOIR Thierry",
        "BEHOGNE François", "WART Hélène", "STOUPY Sarah", "MARQUETTE Laetitia", "FORSTER Jessica",
        "DUBUISSON Brigitte", "DEGRYSE Stéphanie", "LUISE Virginie", "TOTH-BUDAI Mireille", "VESCERA Marie",
        "DENEUFBOURG Camille", "DELMARCHE Caroline", "CUVELIER Philippe", "DESART Vincent", "AUTHELET Pascal",
        "WéRY Alain", "BAKOLAS Virginie", "VANDENBRANDE Francine", "LAMBERT Sandrine", "STAGNITTO Elodie",
        "SCELFO Valérie", "COLLART Luc", "MOHYMONT Frédéric", "LECLERCQ Isabelle", "COUDOU Laurence",
        "BEGUIN Christophe", "TRAMASURE Sébastien", "PEDALINO Antoinette", "SCIAMANNA Anne-Catherine"
        "LANCKMANS Laurie", "ALTES SAFONT Manoli Nieves P", "KOTTONG Laura Jeanne M", "KHATMI Iliass",
        "REY Quentin", "GODEFRIDI Marie", "VANDERMEULEN Céline", "FAUCQ Laura", "DOGAN Mustafa Mete",
        "ROLIN Xavier", "OSSIEUR Diane", "HANON DE LOUVET Sandrine", "DELWICHE Emmanuelle",
        "LIGOT Fabienne", "MALGAUD Corinne", "HERRENT Joyce", "BONNET Laurence", "SANS Catherine",
        "DE BOCK Christine", "BALTUS Claude-Alain", "TILQUIN Yvonne", "BUISSERET Laetitia",
        "DE WILDE D'ESTMAEL Coraline", "FEYS Dominique-Andrée", "QUACKELS Françoise",
        "DEBROUX Annick", "REIZER Martin", "BRüCK Valérie", "WALSH David", "LIBOUTON Catherine", "LEDOUX Jean-François",
        "ETIENNE Anne-Joëlle", "SEPULCHRE Jean-Grégoire", "TOTH-BUDAI Mireille", "DELVAUX Christel",
        "VINçOTTE Bernard", "BOGAERTS Michel", "DEMBOUR François", "LANNI Christian", "DELVOIE Pascale",
        "GIROUARD Françoise", "GILLIS Marielle", "NOEL Anne-Cécile", "MASSET Marc", "HOUBEN Marcel", "LOURTIE Chantal",
        "MORDANT Cécile", "BAUDEN Sylvie", "LEJEUNE Julie", "ROBIDA Stéphane", "DANLOY Géraldine",
        "CHARLIER Dominique", "LANNOY Cécile", "DEGUEL François", "LAMCHACHTI Laetitia", "LUYPAERTS Aurélia",
        "BASTIN Bernard", "KRIESCHER Pauline", "FRAIPONT Elisabeth", "DUVEILLER Stéphanie", "DE JONGHE Françoise",
        "DELMOTTE Corinne", "THIRY Sophie", "UHODA Emmanuelle", "GILLET Valérie", "COLLARD Pierre-Yves",
        "LAMALLE Gregory", "DEVENTER Olivier", "JAMMAER Anne-Charlotte", "WALDMANN Jonathan", "JAMMAER Thierry",
        "HUMBLET Dominique", "TRIVINO HENNUY Isabelle", "SCHMITZ Nicolas", "FADEUX François Michel F",
        "GOLINVAUX Justine Myriam G", "COLLIER Delphine", "BRIDOUX Olivier", "LESUISSE Olivier", "POLLAERT Carine",
        "HERRENT Joyce", "DELVAUX Joëlle", "HONORé Joséphine", "LEDOUX Jean-François",
        "VAN DER STEEN Grégory", "PIERRET Sophie", "DELHAYE Françoise", "ELOIN Anne-Cécile", "LAURENT Marlène",
        "BRIX Françoise", "LEDOUX Jean-François", "OLDENHOVE DE GUERTECHIN Pauline", "VAN DER STEEN Grégory",
        "PIERRET Sophie", "DELHAYE Françoise", "ELOIN Anne-Cécile", "LAURENT Marlène", "BRIX Françoise",
        "SCHMITZ Nicolas", "STRAETEN Jean-François", "DUMOULIN Nathalie", "MAGNEE Véronique", "LUYPAERTS Aurélia",
        "MOLITOR Philippe", "HEINS Renaud", "DEWONCK Séverine", "HENKES Astrid", "SCHLENTER Sarah", "KARIOUN Soraya",
        "FRATEUR Maureen", "TOLLENAERE Valérie", "BOONEN Marie-Christine", "FIEUW Fanny", "BASTIEN Stéphanie",
        "FONTAINE Héloïse", "ROOS Virginie", "GODFROID Isabelle", "WESTERLINCK Eléonore", "DANDOY Philippe",
        "GELDERS Laura", "BERCHEM Nicolas", "GODTS Joëlle", "VAN ACKERE Cécile", "FLAHAUT Jérôme",
        "DE WILDE D'ESTMAEL Grégoire", "VRANCX Vanina", "TOUSSAINT Marie", "VROONEN Claudine", "GUILLET Nathalie",
        "LUYCKX Ludivine", "BOUILLIEZ Benjamin", "OLDENHOVE DE GUERTECHIN Pauline", "Ruben JANS", "Marie-Eve Clossen",
        "Amandine LACROIX", "Florence Coulonval", "Gaël D'Hôtel", "Anne-Cécile Clare", "Maxime Dulieu",
        "Laurent POISSON", "Aurélie Rooselaer", "Sophie DREZE", " Marie FABER", " Nicolas DELECLUSE",
        "Véronique QUINET", "Xavier SCHURMANS", "Tanguy KELECOM", "Thibault SACRE", "Marc Masset", "Marie BOONEN",
        "Anne JACMIN", "Ariane REGNIERS", "Gilles GRUSLIN", "Aurélie FOSSION", "Frédérique MAHIEU",
        "Alexandra BENOIT", "Christelle DE BRUYCKER", " Aude LIEVENS", "Catherine DUTRY", "Géraldine Druart",
        "Vincent DUPONT", "Luc VAN KERCKHOVEN", "Bertrand NAMUR", "NUTTIN Julie", "Kensier Aline", "NUTTIN Julie",
        "Cécile VAN ACKERE", "Magalie Debergh", "Alizée BOSSER", "Olivia DE DEKEN", "Xavier BEAUVOIS", "Ermina KUQ",
        "Laurent GUSTIN", "Pascale CARLIER", "Evelyne RAES", "Damien RIDELLE", "Maxime FABRY", "Aline PEREE",
        "Daniel HENNEAUX", "Christine CAVELIER", "Damien EVRARD", "Patricia Brunet", "Laetitia FILLIEUX",
        "Xavier DRION", "Damien VANNESTE", "Clotilde VAN HAEPEREN", "Laurence TILQUIN", "Christine PAERMENTIER",
        "Gérard Hermans", "Gwennaëlle NAVEZ", "Thibaut VANBERSY", "Benjamin DESMET", "Marie LIMBOURG",
        "Benjamin DESMET", "Pierre SCHMITS", "Gilles Oliviers", "Françoise DE JONGHE", "Thomas Mertens",
        "Nathalie LEFEVRE", "Patrick Leclerc", "Pierre Machiels", "Eric TARICCO", "Paul ERNOULD",
        "Anne-Sylvie de BRABANT", "Sébastien CORMAN", "Maître Gwenaëlle BOGAERTS", "Damien DUPUIS",
        "Louise VAN MALLEGHEM", "Colombine ESCARMELLE", "Grégory VAN DER STEEN", "Pierre-Eric DEFRANCE",
        "Doris SALAMON", "Audrey GAROT", "Cédric CUYVERS", "Geoffroy HUEZ", "Déborah FRIES", "Joël CHAPELIER",
        "Yves Paul HENQUET", "Sabine DUQUESNOY", "Murielle DEVILLEZ", "Nicolas BAUDART", "Cécile Carmon",
        "Isabelle RASPE", " Franca GIORNO", "Laurent Rolans", "Gregory VAN DER STEEN", "Stéphanie ROELS",
        "Gregory VAN DER STEEN", "Bénédicte VANOLST", "Marie Dispa", "Christophe HUBERT", "Pierre Lothe",
        "Pauline OLDENHOVE", "Séverine GILLET", "Claude Alain Baltus", "Anne Defour", "Ann Verlaenen",
        "Myriam GEREON", "Gael Thiry", " Etienne BAIJOT", "Laurent GOFFINET", " Daniel ZAMARIOLA", "Klaas ROSSEEL",
        "Joris WINBERG", "Guillaume Delahaye", "Jean-François MONIOTTE", "Isabelle Patris", "Geneviève ADAM",
        "Véronique Vessié", "Cinzia BERTOLIN", "Amélie DERYCKE", "Vinciane PETIT", "Thierry KNOOPS",
        "Anne-Sophie VIVIER", "Christelle DELPLANCQ", "Isabelle GERARD", "Isabelle BALDO", "Benjamin Van Dorpe",
        "Patrick Nedergedaelt", "Dirk Wouters", "Dominique Silance", "François Tumerelle", "Bérengère GUILLAUME",
        "Erika Swysen", "Frédérique BATARDY", "Pauline DURUISSEAU", "Marc JACQUEMOTTE", "Christel SCHOONBROODT",
        "Pascal LAMBERT", "Murielle PIGEOLET", "Lucie LEYDER", "Marijke VAN REYBROUCK", "Laurie LANCKMANS",
        "Anne-Catherine NOIRHOMME", "Petra DIERICKX", "Florence van HOUT", "Céline LABAR", "Léa MARQUIS",
        "Chantal LEKEU", "Nathalie GILLE", "Olivier Dandois", "Deborah SITKOWSKI", "Simon HUBERT",
        "Vincent DE CEUNINCK", "Olivier VERSLYPE", "Béatrice DEGREVE", "Vincent DIEU", "Raphaël PAPART",
        "Virginie GOSSELIN", "Stéphanie Collard", "Veerle Simeons", "Ingrid Goez", "Ingrid Surleau",
        "Sandrine VALVEKENS", "HENROTIN Jean Marie", "GOSSIAUX Marie", "BOSSARD Philippe", "DE RIDDER Karl",
        "MEUNIER Violette", "BRONKAERT Isabelle", "VAUSORT Isabelle", "MAESEELE Lisabeth", "CHARLEZ François",
        "BORN Maxime", "DENèVE Marc", "BONGIORNO Sabrina", "GROFILS Bernard", "HOC Françoise", "CORNIL David",
        "ADAM Marie", "BERNIS Guillaume", "DUSAUCY Vincent", "LEMAIRE Geoffroy", "GLAUDE Bernard", "DEWAIDE Xavier",
        "NOëL Christiane", "BRINGARD Francis", "SCHREDER Philippe-Robert", "GHILAIN Mélanie", "LYAZOULI Karim",
        "DELBRASSINNE Eric", "DELVAUX Christel", "BISINELLA Yves", "FAUFRA Aline", "THIRY Pierre",
        "PAQUOT Jean-Luc", "JACQUINET Barbara", "DELWAIDE Laurent", "MUSCH Charlotte", "STAS DE RICHELLE Laurent",
        "DEWANDRE Caroline", "FRéDéRICK François", "HISSEL Victor", "GUSTINE Olivier", "BIEMAR Isabelle",
        "BIHAIN Luc", "DERROITTE Jean-François", "DESTEXHE Arnaud", "GODFROID Yves", "GEORGE Florence",
        "THIRY Pierre", "PROPS Roland", "ABSIL Adrien", "LEGRAS Pierre", "REMICHE Charlotte", "KERSTENNE Frédéric",
        "CHARLES Xavier", "CAVENAILE Thierry", "BOURLET Pierre-François", "VIESLET Samuel", "VERSIE Béatrice",
        "ESLIK Berivan", "BERTRAND Sophie", "KRZANIK Saskia", "LEVAUX Marc", "MINON François", "PROUMEN Léon-Pierre",
        "NICOLINI Laura", "BOULANGé Pierre", "BILLEN Muriel", "VON FRENCKELL Ingrid", "DECHARNEUX Joëlle",
        "SCALAIS Julien", "CHEN Yuqin", "DELWAIDE Maurice", "HENRY Pierre", "GRIGNARD Didier", "EVRARD Sandrine",
        "DEVYVER Violaine", "RENETTE André", "PAQUOT Jean-Luc", "DAVIN Raphaël", "HUSSON Jean-Marc", "THIRION Valérie",
        "EVRARD Olivier", "BOTTIN Pierre", "DELFORGE Murielle", "YILDIRIM Serife", "BOILEAU Jean", "ERNOTTE Florian",
        "BAERTS Audrey", "FRANCK Edouard", "LACROIX Mary", "BISINELLA Yves", "KAKULYA Mariam", "BAUDINET Laurie",
        "SEINLET Sophie", "RENAUD Jean-Philippe", "NICOLINI Laura", "RENAUD Jean-Philippe", "NICOLINI Laura",
        "CHAMBERLAND Benoit", "CRASSET Renaud Oscar G", "HUART Frédéric", "KAUTEN Marc", "BRULARD Yves",
        "BELLAVIA Tony", "GHILAIN Mélanie", "BRUX Stéphane", "VANDER DONCKT Sophie", "ROUSSEAU Alice", "HENRION Kim",
        "SENECAUT Manuella", "DEHAENE John", "WAEGENAERE Bruno", "BELLAVIA Tony", "RENAUD Jean-Philippe",
        "BUY Julien", "CRAPPE Caroline", "DALLAPICCOLA Jessica", "THIRION Valérie", "REMIENCE Christine",
        "STEINIER Karl", "GYSELINX Jean-Yves", "PHILIPPOT Damien", "OGER Luc", "DELFORGE Murielle",
        "TOUSSAINT Frédérique", "DAVIN Raphaël", "COMBREXELLE Angélique", "HOC Benoît", "ELOY Gaëlle", "DARMONT Benoît",
        "BUCHET Benoît", "SCHOLL Francine", "GEûENS Laurent", "ETIENNE François", "SCHAMPS Alain", "GUSTIN Jean-Max",
        "DEBONNET Victor", "DEHAENE John", "GUSTIN Laurent", "DEMETS Julie", "OPSOMER Thierry", "CAILLEAU Mélisande",
        "MERCIER Olivier-A", "CHANTRY Valentine", "LACROIX Amandine", "CHARLEZ François", "CARION Guillaume",
        "FRITZ Martin", "HENRY Pierre", "THOMAS Paul", "FRéDéRICK François", "LEGRAS Pierre", "PROPS Roland",
        "GILSON Marc", "GERARDY Lucie", "LEGRAND Dominique", "Nathalie BAUDOUR", "Charlotte VESSIE",
        "Aurélie DE WALEFFE", "Valérie Mazy", " Klass ROSSEEL", "Nathalie MASSET", "Charlotte STEVENS",
        "Laurence BURTON", "Chantal BRONLET", "Chantal BRONLET", "Damien PONCELET", "Olivier De Ridder",
        "Laurence ROOSEN", "Bénédicte DELVIGNE", "Alexandre REIJNDERS", "Thibault DELAEY", "Jean-Christophe ANDRE",
        "Sarah BRUYNINCKX", "Graziella MARTINI", "Sylvie GUIMIN", "Céline DEVILLE", "Benoît KETTELS", "Anne LAMBIN",
        "Marjorie WILMOTTE", "Pierre FRANCHIMONT", "Nathalie Leleux", "Murielle Billen",
        "Joséphine Louise Henriette Honoré", "Vincent LIEGEOIS", "Denis DRION", "Jacques LEJEUNE", "Claudine TERWAGNE",
        "Aline Pierrard", "Jean-François LIEGEOIS", "Geert Coene", "Lydia BOUADDOU", "Justine LAMBERT", "Coralie ANQUET",
        "Philippe GODIN", "Emeline HANNIER", "Jean-Luc NAVARRE", "Renaud de BIOURGE", "Marie VANDENPLAS",
        "Isabelle TRIVINO", "Jean-Philippe POCHART", "Laurence LAMBRECHTS", "Corentin LUCIFORA", "Lucie HERMANT",
        "Bruno LECLERCQ", "Manuella COMBLIN", "Catherine HINS", "Cassandra LESSIRE", "Adrien KAISIN", "Valérie PIRSON",
        "Yves DUQUENNE", "Coppieters't Wallant", "Laurie ROMAN", "Hélène PREUMONT", "Valérie SAINT-GHISLAIN",
        "Alessandra BUFFA", "Jolanta KACZOROWSKA", "Fabienne HOECK", "Stéphanie Palate", "Anne-Catherine LEPAGE",
        "Géry DERREVEAUX"
    ]
    # Nettoyage final (utile si tu copies-colles depuis plusieurs sources)
    selected = list(set(curateurs + administrateurs_provisoires))

    if not selected:
        print("❌ Aucune entrée sélectionnée.")
        exit(1)

    action_map = {
        'create': creer_csv,
        'add': ajouter_curateurs,
        'remove': supprimer_curateurs
    }

    action_func = action_map.get(args.action)
    if action_func:
        action_func(selected)
    else:
        print("❌ Action invalide.")
