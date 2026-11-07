# Kontrola podglądu względem referencji

Kontrola ma trzy warstwy. Pierwsza jest lokalna i bezpłatna: format 1080×1920, kodeki, długość, 30 FPS, rytm scen, unikalność assetów, końcowy hold, kolizje mocnych efektów, styl napisów oraz obecność podstawowych elementów języka referencji.

Druga lokalna warstwa to `qa:attention`: wykrywa twarze, obszary podobne do tekstu, mapę saliency i kandydatów okrągłych. Twarz głównego bohatera jest chroniona twardo; drobne twarze widzów, saliency i obiekty okrągłe pozostają ostrzeżeniami, żeby fałszywa detekcja nie blokowała renderu. Plansza przecinająca główną twarz albo główna twarz dotykająca krawędzi kadru zatrzymuje pipeline.

Trzecia warstwa jest semantyczna. Musi potwierdzić, że obraz odpowiada dokładnie wypowiadanym słowom, bohater nie jest ujawniony za wcześnie, akcje dochodzą do kulminacji, tekst nie zakrywa twarzy, a efekty wzmacniają narrację. Lokalny skrypt nie może udawać, że rozumie te kwestie.

Finalny pipeline renderuje najpierw `NAZWA-preview-check.mp4`. Dopiero gdy `qa:attention` i zwykłe bramki lokalne przejdą, plik zastępuje `NAZWA-render.mp4`. Dzięki temu nieudana nowa wersja nie nadpisuje ostatniego poprawnego renderu.

Wynik `pass-local-gates-needs-semantic-review` oznacza przejście kontroli technicznej, a nie automatyczną akceptację filmu. Płatna analiza wideo wymaga osobnego limitu i zgody. Maksymalnie dwie rundy poprawek jednego podglądu.
