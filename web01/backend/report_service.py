from datetime import datetime
from html import escape
from io import BytesIO
import re

from sqlalchemy import select

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from challenges import get_challenge
from config import BASE_POINTS
from models import (
    ChallengeResult,
    Organization,
    SessionChallenge,
    SessionMessage,
    User,
)


PRODUCT_NAME = "BreachOut"

GREEN = colors.HexColor("#35F29A")
DARK_GREEN = colors.HexColor("#0A140F")
BORDER_GREEN = colors.HexColor("#294235")
MUTED = colors.HexColor("#66766D")
LIGHT_BG = colors.HexColor("#F4F8F5")
WARNING_BG = colors.HexColor("#FFF8E8")


def format_datetime(
    value: datetime | None
) -> str:
    if not value:
        return "-"

    try:
        value = value.astimezone()
    except Exception:
        pass

    return value.strftime(
        "%d-%m-%Y %H:%M"
    )


def format_duration(
    started_at: datetime | None,
    completed_at: datetime | None,
) -> str:
    if not started_at:
        return "-"

    end = (
        completed_at
        or datetime.now(
            started_at.tzinfo
        )
    )

    try:
        seconds = max(
            0,
            int(
                (
                    end
                    - started_at
                ).total_seconds()
            )
        )
    except Exception:
        return "-"

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours:
        return (
            f"{hours} uur "
            f"{minutes} min"
        )

    if minutes:
        return (
            f"{minutes} min "
            f"{seconds} sec"
        )

    return f"{seconds} sec"


def status_label(
    status: str | None
) -> str:
    labels = {
        "active": "Actief",
        "completed": "Voltooid",
        "cancelled": "Geannuleerd",
        "pending": "Wachtend",
        "skipped": "Overgeslagen",
    }

    return labels.get(
        status or "",
        status or "-"
    )


def mode_label(
    mode: str | None
) -> str:
    if mode == "single":
        return "Losse challenge"

    if mode == "package":
        return "Challengepakket"

    return mode or "-"


def safe_filename_part(
    value: str
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        value.strip()
    )

    cleaned = cleaned.strip(
        "-"
    )

    return (
        cleaned
        or "team"
    )


def paragraph(
    value,
    style
) -> Paragraph:
    return Paragraph(
        escape(
            str(
                value
                if value is not None
                else "-"
            )
        ),
        style,
    )


def build_session_report(
    db,
    game_session
) -> tuple[bytes, str]:
    """
    Bouw een klantgericht BreachOut PDF-rapport.

    Alleen de API bepaalt wie dit rapport mag downloaden.
    Deze service bevat bewust geen autorisatielogica.
    """

    team = db.get(
        User,
        game_session.user_id
    )

    organization = None

    if game_session.organization_id:
        organization = db.get(
            Organization,
            game_session.organization_id
        )

    starter = None

    if game_session.started_by_user_id:
        starter = db.get(
            User,
            game_session.started_by_user_id
        )

    session_challenges = list(
        db.scalars(
            select(SessionChallenge)
            .where(
                SessionChallenge.session_id
                == game_session.id
            )
            .order_by(
                SessionChallenge.position.asc()
            )
        ).all()
    )

    results = list(
        db.scalars(
            select(ChallengeResult)
            .where(
                ChallengeResult.session_id
                == game_session.id
            )
            .order_by(
                ChallengeResult.started_at.asc()
            )
        ).all()
    )

    messages = list(
        db.scalars(
            select(SessionMessage)
            .where(
                SessionMessage.session_id
                == game_session.id
            )
            .order_by(
                SessionMessage.created_at.asc()
            )
        ).all()
    )

    result_map = {
        result.challenge_id: result
        for result in results
    }

    total_points = sum(
        int(
            result.points
            or 0
        )
        for result in results
        if result.completed
    )

    completed_count = sum(
        1
        for result in results
        if result.completed
    )

    wrong_attempts = sum(
        int(
            result.wrong_attempts
            or 0
        )
        for result in results
    )

    hints_used = sum(
        int(
            result.hints_used
            or 0
        )
        for result in results
    )

    if session_challenges:
        max_points = sum(
            int(
                item.max_points
                or BASE_POINTS
            )
            for item in session_challenges
        )
    else:
        max_points = (
            int(
                game_session.total_challenges
                or len(results)
                or 1
            )
            * BASE_POINTS
        )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=(
            f"{PRODUCT_NAME} Resultatenrapport"
        ),
        author=PRODUCT_NAME,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BreachOutTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=29,
        textColor=DARK_GREEN,
        spaceAfter=4 * mm,
    )

    subtitle_style = ParagraphStyle(
        "BreachOutSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=MUTED,
        spaceAfter=8 * mm,
    )

    heading_style = ParagraphStyle(
        "BreachOutHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=DARK_GREEN,
        spaceBefore=4 * mm,
        spaceAfter=3 * mm,
    )

    body_style = ParagraphStyle(
        "BreachOutBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor(
            "#243029"
        ),
    )

    small_style = ParagraphStyle(
        "BreachOutSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )

    info_label_style = ParagraphStyle(
        "BreachOutInfoLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(
            "#17492F"
        ),
    )

    info_value_style = ParagraphStyle(
        "BreachOutInfoValue",
        parent=body_style,
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor(
            "#17231C"
        ),
    )

    table_header_style = ParagraphStyle(
        "BreachOutTableHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    number_style = ParagraphStyle(
        "BreachOutNumber",
        parent=body_style,
        fontName="Helvetica-Bold",
        alignment=TA_RIGHT,
    )

    story = []

    story.append(
        Paragraph(
            "Breach<span color='#35F29A'>Out</span>",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "Resultatenrapport cybersecurity-sessie",
            subtitle_style,
        )
    )

    # =====================================================
    # Algemene sessiegegevens
    # =====================================================

    story.append(
        Paragraph(
            "Sessiegegevens",
            heading_style,
        )
    )

    info_data = [
        [
            paragraph(
                "Team",
                info_label_style
            ),
            paragraph(
                team.display_name
                if team
                else game_session.user_id,
                info_value_style
            ),
            paragraph(
                "Bedrijf",
                info_label_style
            ),
            paragraph(
                organization.name
                if organization
                else "Niet gekoppeld",
                info_value_style
            ),
        ],
        [
            paragraph(
                "Type sessie",
                info_label_style
            ),
            paragraph(
                mode_label(
                    game_session.mode
                ),
                info_value_style
            ),
            paragraph(
                "Status",
                info_label_style
            ),
            paragraph(
                status_label(
                    game_session.status
                ),
                info_value_style
            ),
        ],
        [
            paragraph(
                "Gestart",
                info_label_style
            ),
            paragraph(
                format_datetime(
                    game_session.started_at
                ),
                info_value_style
            ),
            paragraph(
                "Afgerond",
                info_label_style
            ),
            paragraph(
                format_datetime(
                    game_session.completed_at
                ),
                info_value_style
            ),
        ],
        [
            paragraph(
                "Duur",
                info_label_style
            ),
            paragraph(
                format_duration(
                    game_session.started_at,
                    game_session.completed_at,
                ),
                info_value_style
            ),
            paragraph(
                "Gestart door",
                info_label_style
            ),
            paragraph(
                starter.display_name
                if starter
                else "-",
                info_value_style
            ),
        ],
    ]

    info_table = Table(
        info_data,
        colWidths=[
            27 * mm,
            60 * mm,
            27 * mm,
            60 * mm,
        ],
    )

    info_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#E9F7EF"),
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#E9F7EF"),
            ),
            (
                "BACKGROUND",
                (1, 0),
                (1, -1),
                colors.white,
            ),
            (
                "BACKGROUND",
                (3, 0),
                (3, -1),
                colors.white,
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                BORDER_GREEN,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.HexColor(
                    "#D8E2DC"
                ),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
        ])
    )

    story.append(
        info_table
    )

    story.append(
        Spacer(
            1,
            7 * mm
        )
    )

    # =====================================================
    # Samenvatting
    # =====================================================

    story.append(
        Paragraph(
            "Samenvatting",
            heading_style,
        )
    )

    summary_data = [
        [
            paragraph(
                "Voltooid",
                small_style
            ),
            paragraph(
                "Score",
                small_style
            ),
            paragraph(
                "Foute antwoorden",
                small_style
            ),
            paragraph(
                "Ingebouwde hints",
                small_style
            ),
        ],
        [
            paragraph(
                f"{completed_count} / "
                f"{game_session.total_challenges}",
                number_style
            ),
            paragraph(
                f"{total_points} / {max_points}",
                number_style
            ),
            paragraph(
                wrong_attempts,
                number_style
            ),
            paragraph(
                hints_used,
                number_style
            ),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            43.5 * mm,
            43.5 * mm,
            43.5 * mm,
            43.5 * mm,
        ],
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                DARK_GREEN,
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor(
                    "#F7FBF8"
                ),
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                BORDER_GREEN,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.HexColor(
                    "#D8E2DC"
                ),
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER",
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
        ])
    )

    story.append(
        summary_table
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    # =====================================================
    # Challenge resultaten
    # =====================================================

    story.append(
        Paragraph(
            "Resultaten per challenge",
            heading_style,
        )
    )

    challenge_rows = [
        [
            paragraph(
                "#",
                table_header_style
            ),
            paragraph(
                "Challenge",
                table_header_style
            ),
            paragraph(
                "Niveau",
                table_header_style
            ),
            paragraph(
                "Fouten",
                table_header_style
            ),
            paragraph(
                "Hints",
                table_header_style
            ),
            paragraph(
                "Punten",
                table_header_style
            ),
            paragraph(
                "Status",
                table_header_style
            ),
        ]
    ]

    if session_challenges:
        iterable = [
            (
                item.position,
                item.challenge_id,
                item.difficulty_level,
                item.status,
            )
            for item in session_challenges
        ]
    else:
        iterable = [
            (
                index,
                result.challenge_id,
                (
                    get_challenge(
                        result.challenge_id
                    )
                    or {}
                ).get(
                    "difficulty_level",
                    "-"
                ),
                (
                    "completed"
                    if result.completed
                    else "pending"
                ),
            )
            for index, result in enumerate(
                results,
                start=1
            )
        ]

    for (
        position,
        challenge_id,
        difficulty_level,
        challenge_status,
    ) in iterable:
        result = result_map.get(
            challenge_id
        )

        challenge = (
            get_challenge(
                challenge_id
            )
            or {}
        )

        name = challenge.get(
            "name",
            challenge_id
        )

        category = challenge.get(
            "category",
            "-"
        )

        challenge_name = Paragraph(
            (
                f"<b>{escape(str(name))}</b>"
                f"<br/>"
                f"<font size='7' color='#66766D'>"
                f"{escape(str(category))}"
                f"</font>"
            ),
            body_style,
        )

        challenge_rows.append([
            paragraph(
                position,
                body_style
            ),
            challenge_name,
            paragraph(
                difficulty_level,
                body_style
            ),
            paragraph(
                (
                    result.wrong_attempts
                    if result
                    else 0
                ),
                body_style
            ),
            paragraph(
                (
                    result.hints_used
                    if result
                    else 0
                ),
                body_style
            ),
            paragraph(
                (
                    result.points
                    if result
                    else 0
                ),
                body_style
            ),
            paragraph(
                status_label(
                    (
                        "completed"
                        if (
                            result
                            and result.completed
                        )
                        else challenge_status
                    )
                ),
                body_style
            ),
        ])

    challenge_table = Table(
        challenge_rows,
        repeatRows=1,
        colWidths=[
            10 * mm,
            57 * mm,
            20 * mm,
            18 * mm,
            18 * mm,
            18 * mm,
            25 * mm,
        ],
    )

    challenge_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                DARK_GREEN,
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                BORDER_GREEN,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.HexColor(
                    "#DDE5E0"
                ),
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    LIGHT_BG,
                ],
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "ALIGN",
                (0, 1),
                (0, -1),
                "CENTER",
            ),
            (
                "ALIGN",
                (2, 1),
                (-1, -1),
                "CENTER",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
        ])
    )

    story.append(
        challenge_table
    )

    # =====================================================
    # Spelleider communicatie
    # =====================================================

    if messages:
        story.append(
            Spacer(
                1,
                8 * mm
            )
        )

        story.append(
            Paragraph(
                "Begeleiding door de Spelleider",
                heading_style,
            )
        )

        message_rows = [
            [
                paragraph(
                    "Tijd",
                    table_header_style
                ),
                paragraph(
                    "Type",
                    table_header_style
                ),
                paragraph(
                    "Challenge",
                    table_header_style
                ),
                paragraph(
                    "Bericht",
                    table_header_style
                ),
            ]
        ]

        for message in messages:
            challenge_name = "-"

            if message.challenge_id:
                challenge = (
                    get_challenge(
                        message.challenge_id
                    )
                    or {}
                )

                challenge_name = (
                    challenge.get(
                        "name",
                        message.challenge_id
                    )
                )

            message_rows.append([
                paragraph(
                    format_datetime(
                        message.created_at
                    ),
                    small_style
                ),
                paragraph(
                    (
                        "Hint"
                        if (
                            message.message_type
                            == "hint"
                        )
                        else "Bericht"
                    ),
                    body_style
                ),
                paragraph(
                    challenge_name,
                    body_style
                ),
                paragraph(
                    message.message,
                    body_style
                ),
            ])

        message_table = Table(
            message_rows,
            repeatRows=1,
            colWidths=[
                31 * mm,
                21 * mm,
                45 * mm,
                77 * mm,
            ],
        )

        message_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    DARK_GREEN,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER_GREEN,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor(
                        "#DDE5E0"
                    ),
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        WARNING_BG,
                    ],
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ])
        )

        story.append(
            message_table
        )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            (
                "Puntenmodel: iedere challenge start op "
                f"{BASE_POINTS} punten. Een fout antwoord kost "
                "1 punt en een ingebouwde hint kost 2 punten. "
                "Hints die door de Spelleider worden verstuurd "
                "hebben geen puntenaftrek."
            ),
            small_style,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm
        )
    )

    story.append(
        Paragraph(
            (
                "Rapport gegenereerd op "
                f"{format_datetime(datetime.now().astimezone())}."
            ),
            small_style,
        )
    )

    def add_page_footer(
        canvas,
        doc
    ):
        canvas.saveState()

        canvas.setStrokeColor(
            colors.HexColor(
                "#D8E2DC"
            )
        )

        canvas.line(
            18 * mm,
            14 * mm,
            A4[0] - 18 * mm,
            14 * mm,
        )

        canvas.setFont(
            "Helvetica",
            7
        )

        canvas.setFillColor(
            MUTED
        )

        canvas.drawString(
            18 * mm,
            9 * mm,
            (
                "BreachOut - "
                "Cybersecurity Challenge Platform"
            ),
        )

        canvas.drawRightString(
            A4[0] - 18 * mm,
            9 * mm,
            f"Pagina {doc.page}",
        )

        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_footer,
        onLaterPages=add_page_footer,
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()

    team_name = (
        team.display_name
        if team
        else "team"
    )

    date_part = (
        game_session.started_at.strftime(
            "%Y-%m-%d"
        )
        if game_session.started_at
        else "rapport"
    )

    filename = (
        "BreachOut-rapport-"
        f"{safe_filename_part(team_name)}-"
        f"{date_part}.pdf"
    )

    return (
        pdf_bytes,
        filename,
    )
