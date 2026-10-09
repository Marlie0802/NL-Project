(() => {

    const params =
        new URLSearchParams(
            window.location.search
        );

    const sessionId =
        params.get("session");


    if (!sessionId) {
        return;
    }


    const style =
        document.createElement(
            "style"
        );

    style.textContent = `
        #challengelab-hint-button {
            position: fixed;
            right: 20px;
            bottom: 20px;
            z-index: 9999;

            border: 1px solid #35f29a;
            border-radius: 9px;

            background: #0b1710;
            color: #35f29a;

            padding: 12px 16px;

            font-family: Arial, sans-serif;
            font-weight: bold;

            cursor: pointer;
        }

        #challengelab-hint-button:hover {
            background: #102219;
        }

        #challengelab-hint-panel {
            position: fixed;

            right: 20px;
            bottom: 75px;

            z-index: 9998;

            width: 380px;
            max-width: calc(100vw - 40px);

            padding: 18px;

            border: 1px solid #294c38;
            border-radius: 11px;

            background: #08130d;
            color: #e8f2ec;

            font-family: Arial, sans-serif;

            box-shadow:
                0 15px 40px
                rgba(0,0,0,.45);

            display: none;
        }

        #challengelab-hint-panel strong {
            color: #35f29a;
        }

        #challengelab-hint-meta {
            color: #829088;

            font-size: 12px;

            margin-top: 12px;
        }
    `;

    document.head.appendChild(
        style
    );


    const panel =
        document.createElement(
            "div"
        );

    panel.id =
        "challengelab-hint-panel";


    const button =
        document.createElement(
            "button"
        );

    button.id =
        "challengelab-hint-button";

    button.textContent =
        "Hint (-2 punten)";


    document.body.appendChild(
        panel
    );

    document.body.appendChild(
        button
    );


    button.addEventListener(
        "click",
        async () => {

            const confirmed =
                confirm(
                    "Een hint kost 2 punten.\n\n" +
                    "Wil je de volgende hint bekijken?"
                );

            if (!confirmed) {
                return;
            }


            button.disabled = true;


            try {

                const response =
                    await fetch(
                        "/api/session/" +
                        encodeURIComponent(
                            sessionId
                        ) +
                        "/hint",
                        {
                            method: "POST",
                            credentials:
                                "same-origin"
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Hint kon niet worden geladen."
                    );
                }


                panel.style.display =
                    "block";


                if (!data.available) {

                    panel.innerHTML = `
                        <strong>
                            Geen hints meer
                        </strong>

                        <p>
                            Je hebt alle beschikbare hints
                            voor deze challenge gebruikt.
                        </p>

                        <div id="challengelab-hint-meta">
                            Mogelijke score:
                            ${data.potential_points}
                            punten
                        </div>
                    `;

                    button.textContent =
                        "Geen hints meer";

                    button.disabled =
                        true;

                    return;
                }


                panel.innerHTML = `
                    <strong>
                        Hint ${data.hint_number}
                        / ${data.total_hints}
                    </strong>

                    <p>
                        ${escapeHint(
                            data.hint
                        )}
                    </p>

                    <div id="challengelab-hint-meta">
                        -${data.penalty} punten ·
                        Deze challenge is nu maximaal
                        ${data.potential_points} punten waard.
                    </div>
                `;


                if (
                    data.hint_number
                    >= data.total_hints
                ) {

                    button.textContent =
                        "Alle hints gebruikt";

                } else {

                    button.textContent =
                        "Volgende hint (-2)";
                }


            } catch (error) {

                alert(
                    error.message
                );

            } finally {

                if (
                    button.textContent
                    !== "Geen hints meer"
                ) {
                    button.disabled =
                        false;
                }
            }
        }
    );


    function escapeHint(value) {

        return String(value)

            .replaceAll(
                "&",
                "&amp;"
            )

            .replaceAll(
                "<",
                "&lt;"
            )

            .replaceAll(
                ">",
                "&gt;"
            )

            .replaceAll(
                '"',
                "&quot;"
            )

            .replaceAll(
                "'",
                "&#039;"
            );
    }

})();
