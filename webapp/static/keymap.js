/* Carte des touches — le strict minimum que HTMX et le HTML natif ne couvrent pas.
   Entrée valide (soumission native du formulaire), le reste est ici :
     - Échap ferme le panneau d'édition
     - un clic hors du panneau le ferme
     - le champ « action » prend le focus à l'ouverture
   Aucune dépendance : on reste sur le fonctionnement 100 % hors-ligne du projet. */
(function () {
    var editor = document.getElementById("key-editor");
    if (!editor) return;

    function close() {
        editor.innerHTML = "";
    }

    /* `autofocus` n'est pas réappliqué sur un fragment inséré après coup :
       on place le focus nous-mêmes une fois le panneau échangé. */
    document.body.addEventListener("htmx:afterSwap", function (e) {
        if (e.target !== editor) return;
        var first = editor.querySelector("input[name='action']");
        if (first) first.focus();
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && editor.innerHTML.trim()) close();
    });

    editor.addEventListener("click", function (e) {
        if (e.target.closest("[data-editor-close]")) close();
    });

    document.addEventListener("click", function (e) {
        if (!editor.innerHTML.trim()) return;
        /* Un clic sur un keycap ouvre un autre panneau : c'est HTMX qui remplace
           le contenu, on ne ferme pas nous-mêmes (sinon on annule l'ouverture). */
        if (e.target.closest("#key-editor") || e.target.closest(".keycap")) return;
        close();
    });
})();
