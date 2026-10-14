(() => {
    "use strict";

    const params =
        new URLSearchParams(
            window.location.search
        );

    const sessionId =
        params.get("session");

    if (!sessionId) {
        return;
    }


    /* =========================================
       INSTELLINGEN
    ========================================= */

    const MESSAGE_INTERVAL = 4000;

    const messageStorageKey =
        `challengelab_message_id_${sessionId}`;

    let lastMessageId = Number(
        localStorage.getItem(
            messageStorageKey
        ) || 0
    );

    let messageTimer = null;


    /* =========================================
       CSS
    ========================================= */

    const style =
        document.createElement(
            "style"
        );

    style.textContent = `
        #breachout-hint-button {
            position: fixed;
            right: 20px;
            bottom: 20px;
            z-index: 99999;

            border: 1px solid #35f29a;
            border-radius: 9px;

            background: #0b1710;
            color: #35f29a;

            padding: 12px 16px;

            font-family: Arial, sans-serif;
            font-size: 14px;
            font-weight: 700;

            cursor: pointer;

            box-shadow:
                0 8px 25px
                rgba(0, 0, 0, .25);
        }

        #breachout-hint-button:hover {
            background: #102219;
        }

        #breachout-hint-button:disabled {
            opacity: .55;
            cursor: not-allowed;
        }


        #breachout-hint-panel {
            position: fixed;

            right: 20px;
            bottom: 76px;

            z-index: 99998;

            width: 390px;
            max-width: calc(100vw - 40px);

            padding: 18px;

            border: 1px solid #294c38;
            border-radius: 11px;

            background: #08130d;
            color: #e8f2ec;

            font-family: Arial, sans-serif;

            box-shadow:
                0 15px 45px
                rgba(0, 0, 0, .48);

            display: none;
        }

        #breachout-hint-panel strong {
            color: #35f29a;
        }

        #breachout-hint-panel p {
            margin:
                12px 0
                0;

            line-height: 1.55;
        }

        .breachout-hint-meta {
            margin-top: 13px;

            color: #829088;

            font-size: 12px;
            line-height: 1.45;
        }


        #breachout-messages {
            position: fixed;

            left: 20px;
            bottom: 20px;

            z-index: 100000;

            width: 390px;
            max-width: calc(100vw - 40px);

            display: flex;
            flex-direction: column;

            gap: 10px;

            pointer-events: none;
        }


        .breachout-message {
            padding: 15px 17px;

            border: 1px solid #2c4a3a;
            border-radius: 10px;

            background: #08130d;
            color: #edf4ef;

            font-family: Arial, sans-serif;

            box-shadow:
                0 12px 35px
                rgba(0, 0, 0, .45);

            pointer-events: auto;

            animation:
                breachout-message-in
                .22s ease-out;
        }


        .breachout-message.hint {
            border-color:
                rgba(
                    255,
                    197,
                    82,
                    .45
                );

            background:
                #17150b;
        }


        .breachout-message-header {
            display: flex;

            align-items: center;
            justify-content: space-between;

            gap: 12px;

            margin-bottom: 8px;
        }


        .breachout-message-label {
            color: #35f29a;

            font-size: 11px;
            font-weight: 700;

            letter-spacing: .8px;
            text-transform: uppercase;
        }


        .breachout-message.hint
        .breachout-message-label {
            color: #ffd071;
        }


        .breachout-message-time {
            color: #718078;

            font-size: 11px;
        }


        .breachout-message-text {
            line-height: 1.5;

            font-size: 14px;
        }


        .breachout-message-close {
            margin-top: 11px;

            padding: 0;

            border: 0;

            background: transparent;
            color: #718078;

            font-size: 12px;

            cursor: pointer;
        }


        .breachout-message-close:hover {
            color: white;
        }


        @keyframes breachout-message-in {
            from {
                opacity: 0;
                transform:
                    translateY(10px);
            }

            to {
                opacity: 1;
                transform:
                    translateY(0);
            }
        }


        @media (max-width: 600px) {
            #breachout-hint-button {
                right: 12px;
                bottom: 12px;
            }

            #breachout-hint-panel {
                right: 12px;
                bottom: 68px;

                max-width:
                    calc(
                        100vw - 24px
                    );
            }

            #breachout-messages {
                left: 12px;
                bottom: 70px;

                max-width:
                    calc(
                        100vw - 24px
                    );
            }
        }
    `;

    document.head.appendChild(
        style
    );


    /* =========================================
       HINT UI
    ========================================= */

    const hintPanel =
        document.createElement(
            "div"
        );

    hintPanel.id =
        "breachout-hint-panel";


    const hintButton =
        document.createElement(
            "button"
        );

    hintButton.id =
        "breachout-hint-button";

    hintButton.type =
        "button";

    hintButton.textContent =
        "Hint (-2 punten)";


    document.body.appendChild(
        hintPanel
    );

    document.body.appendChild(
        hintButton
    );


    hintButton.addEventListener(
        "click",
        requestHint
    );


    async function requestHint() {
        const confirmed =
            confirm(
                "Een ingebouwde hint kost 2 punten.\n\n" +
                "Wil je de volgende hint bekijken?"
            );

        if (!confirmed) {
            return;
        }

        hintButton.disabled = true;

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

            hintPanel.style.display =
                "block";


            if (!data.available) {
                hintPanel.innerHTML = `
                    <strong>
                        Geen hints meer
                    </strong>

                    <p>
                        Je hebt alle ingebouwde hints
                        voor deze challenge gebruikt.
                    </p>

                    <div class="breachout-hint-meta">
                        Mogelijke score:
                        ${
                            data.score
                                ?.potential_points
                            ?? "-"
                        }
                        punten
                    </div>
                `;

                hintButton.textContent =
                    "Alle hints gebruikt";

                hintButton.disabled =
                    true;

                return;
            }


            const possibleScore =
                data.score
                    ?.potential_points
                ?? "-";


            hintPanel.innerHTML = `
                <strong>
                    Hint
                    ${data.hint_number}
                    /
                    ${data.total_hints}
                </strong>

                <p>
                    ${escapeHtml(
                        data.hint
                    )}
                </p>

                <div class="breachout-hint-meta">
                    Deze ingebouwde hint kost
                    2 punten.<br>

                    Mogelijke score voor deze
                    challenge:
                    ${possibleScore}
                    punten.
                </div>
            `;


            if (
                data.hint_number
                >= data.total_hints
            ) {
                hintButton.textContent =
                    "Alle hints gebruikt";

                hintButton.disabled =
                    true;

            } else {
                hintButton.textContent =
                    "Volgende hint (-2)";
            }

        } catch (error) {
            alert(
                error.message
            );

        } finally {
            if (
                hintButton.textContent
                !== "Alle hints gebruikt"
            ) {
                hintButton.disabled =
                    false;
            }
        }
    }


    /* =========================================
       SPELLEIDERBERICHTEN
    ========================================= */

    const messagesContainer =
        document.createElement(
            "div"
        );

    messagesContainer.id =
        "breachout-messages";

    document.body.appendChild(
        messagesContainer
    );


    async function pollMessages() {
        try {
            const response =
                await fetch(
                    "/api/session/" +
                    encodeURIComponent(
                        sessionId
                    ) +
                    "/messages?after_id=" +
                    encodeURIComponent(
                        lastMessageId
                    ),
                    {
                        credentials:
                            "same-origin"
                    }
                );

            if (!response.ok) {
                /*
                 * Bij verlopen login of gestopte sessie
                 * hoeven we de challengepagina niet vol
                 * foutmeldingen te zetten.
                 */
                return;
            }

            const data =
                await response.json();


            if (
                !Array.isArray(
                    data.messages
                )
            ) {
                return;
            }


            for (
                const message
                of data.messages
            ) {
                showGameleaderMessage(
                    message
                );
            }


            if (data.last_id) {
                lastMessageId =
                    Number(
                        data.last_id
                    );

                localStorage.setItem(
                    messageStorageKey,
                    String(
                        lastMessageId
                    )
                );
            }

        } catch {
            /*
             * Tijdelijke netwerkproblemen worden
             * stil genegeerd. Bij de volgende poll
             * probeert de widget het opnieuw.
             */
        }
    }


    function showGameleaderMessage(
        message
    ) {
        const element =
            document.createElement(
                "div"
            );

        element.className =
            "breachout-message" +
            (
                message.type === "hint"
                ? " hint"
                : ""
            );


        const label =
            message.type === "hint"
            ? "Hint van de Spelleider"
            : "Bericht van de Spelleider";


        element.innerHTML = `
            <div class="breachout-message-header">

                <span class="breachout-message-label">
                    ${escapeHtml(
                        label
                    )}
                </span>

                <span class="breachout-message-time">
                    ${escapeHtml(
                        formatTime(
                            message.created_at
                        )
                    )}
                </span>

            </div>

            <div class="breachout-message-text">
                ${escapeHtml(
                    message.text
                )}
            </div>

            <button
                class="breachout-message-close"
                type="button"
            >
                Sluiten
            </button>
        `;


        element
            .querySelector(
                ".breachout-message-close"
            )
            .addEventListener(
                "click",
                () => {
                    element.remove();
                }
            );


        messagesContainer.prepend(
            element
        );
    }


    /* =========================================
       HELPERS
    ========================================= */

    function formatTime(
        value
    ) {
        if (!value) {
            return "";
        }

        const date =
            new Date(
                value
            );

        if (
            Number.isNaN(
                date.getTime()
            )
        ) {
            return "";
        }

        return date.toLocaleTimeString(
            "nl-NL",
            {
                hour: "2-digit",
                minute: "2-digit"
            }
        );
    }


    function escapeHtml(
        value
    ) {
        return String(
            value ?? ""
        )
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


    /* =========================================
       START
    ========================================= */

    pollMessages();

    messageTimer =
        setInterval(
            pollMessages,
            MESSAGE_INTERVAL
        );


    window.addEventListener(
        "beforeunload",
        () => {
            if (messageTimer) {
                clearInterval(
                    messageTimer
                );
            }
        }
    );

})();
