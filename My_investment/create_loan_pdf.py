# -*- coding: utf-8 -*-
"""가족간 차용증 PDF 생성"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

FONT_REG = "Malgun"
FONT_BOLD = "MalgunBold"
pdfmetrics.registerFont(TTFont(FONT_REG, r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont(FONT_BOLD, r"C:\Windows\Fonts\malgunbd.ttf"))

OUT = Path(__file__).resolve().parent / "차용증_조효정_조효진.pdf"


def styles():
    return {
        "title": ParagraphStyle(
            "title",
            fontName=FONT_BOLD,
            fontSize=20,
            leading=28,
            alignment=1,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=FONT_REG,
            fontSize=10,
            leading=14,
            alignment=1,
            textColor="#444444",
            spaceAfter=12,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=FONT_REG,
            fontSize=10.5,
            leading=17,
            alignment=0,
            spaceAfter=4,
        ),
        "article": ParagraphStyle(
            "article",
            fontName=FONT_BOLD,
            fontSize=11,
            leading=17,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "clause": ParagraphStyle(
            "clause",
            fontName=FONT_REG,
            fontSize=10.5,
            leading=16.5,
            leftIndent=8,
            spaceAfter=2,
        ),
        "center": ParagraphStyle(
            "center",
            fontName=FONT_REG,
            fontSize=10.5,
            leading=17,
            alignment=1,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "sign_label": ParagraphStyle(
            "sign_label",
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=15,
        ),
        "sign_body": ParagraphStyle(
            "sign_body",
            fontName=FONT_REG,
            fontSize=10,
            leading=15,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName=FONT_REG,
            fontSize=8.5,
            leading=12,
            textColor="#666666",
            spaceBefore=8,
        ),
    }


def build():
    s = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="차용증",
        author="조효정·조효진",
    )

    story = []
    story.append(Paragraph("차&nbsp;&nbsp;용&nbsp;&nbsp;증", s["title"]))
    story.append(Paragraph("금전소비대차계약서", s["subtitle"]))
    story.append(
        HRFlowable(width="100%", thickness=1.2, color="#222222", spaceAfter=10)
    )

    story.append(
        Paragraph(
            "채권자(대여인): <b>조효정</b>&nbsp;&nbsp;&nbsp;&nbsp;"
            "채무자(차용인): <b>조효진</b>",
            s["center"],
        )
    )
    story.append(
        Paragraph(
            "위 당사자는 다음과 같이 금전소비대차계약을 체결하고, "
            "이를 증명하기 위하여 본 차용증을 작성한다.",
            s["body"],
        )
    )

    story.append(Paragraph("제1조 (차용금액)", s["article"]))
    story.append(
        Paragraph(
            "채무자는 채권자로부터 <b>금 이억원정(￦200,000,000)</b>을 차용한다.",
            s["clause"],
        )
    )

    story.append(Paragraph("제2조 (교부방법 및 일자)", s["article"]))
    story.append(
        Paragraph(
            "위 차용금은 <b>2026년 7월 15일</b> 채권자의 예금계좌에서 채무자의 "
            "예금계좌로 <b>계좌이체</b>의 방법으로 교부되었으며, 채무자는 이를 "
            "틀림없이 수령하였음을 확인한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "· 채권자 계좌: ______________________________ (은행명 / 계좌번호 / 예금주)",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "· 채무자 계좌: ______________________________ (은행명 / 계좌번호 / 예금주)",
            s["clause"],
        )
    )

    story.append(Paragraph("제3조 (이자)", s["article"]))
    story.append(
        Paragraph(
            "① 이 차용금의 이율은 <b>연 3%(연삼퍼센트)</b>로 한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "② 이자는 <b>매월 금 오십만원정(￦500,000)</b>으로 하고, "
            "<b>매월 말일</b>까지 채권자가 지정하는 계좌로 지급한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "③ 이자 지급 개시일은 <b>2026년 8월 31일</b>로 한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "④ 연체 시에는 연체된 이자에 대하여 민법상 법정이율(연 5%)에 따른 "
            "지연이자를 가산할 수 있다.",
            s["clause"],
        )
    )

    story.append(Paragraph("제4조 (변제기한)", s["article"]))
    story.append(
        Paragraph(
            "채무자는 차용원금을 <b>2046년 7월 15일</b>까지 채권자에게 상환한다.",
            s["clause"],
        )
    )

    story.append(Paragraph("제5조 (변제방법)", s["article"]))
    story.append(
        Paragraph(
            "원금 및 이자는 채권자 명의의 아래 계좌로 입금하는 방법으로 변제한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "· 입금계좌: ______________________________ (은행명 / 계좌번호 / 예금주 조효정)",
            s["clause"],
        )
    )

    story.append(Paragraph("제6조 (중도상환)", s["article"]))
    story.append(
        Paragraph(
            "채무자는 원금의 전부 또는 일부를 중도상환할 수 있으며, 중도상환에 따른 "
            "별도의 수수료는 없다. 다만, 이미 발생한 이자는 중도상환일까지 정산하여 지급한다.",
            s["clause"],
        )
    )

    story.append(Paragraph("제7조 (기한의 이익 상실)", s["article"]))
    story.append(
        Paragraph(
            "채무자에게 다음 각 호의 사유가 발생한 경우, 채무자는 기한의 이익을 상실하고 "
            "채권자는 즉시 원금 및 미지급 이자의 상환을 청구할 수 있다.",
            s["clause"],
        )
    )
    story.append(Paragraph("1. 이자 지급을 2회 이상 지체한 경우", s["clause"]))
    story.append(
        Paragraph(
            "2. 강제집행, 파산, 회생절차 개시 신청 등이 있는 경우",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "3. 기타 채권자의 채권보전에 중대한 지장이 생긴 경우",
            s["clause"],
        )
    )

    story.append(Paragraph("제8조 (담보)", s["article"]))
    story.append(
        Paragraph(
            "본 차용에 대하여 <b>연대보증인 등 별도의 담보를 설정하지 아니한다.</b>",
            s["clause"],
        )
    )

    story.append(Paragraph("제9조 (특약)", s["article"]))
    story.append(
        Paragraph(
            "1. 본 계약은 가족 간 금전소비대차임을 확인하며, 증여가 아님을 명확히 한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "2. 이체내역, 이자 입금내역 등 증빙자료는 각 당사자가 보관한다.",
            s["clause"],
        )
    )
    story.append(
        Paragraph(
            "3. 본 계약서에 정하지 않은 사항은 민법 등 관련 법령 및 일반 관례에 따른다.",
            s["clause"],
        )
    )

    story.append(Paragraph("제10조 (분쟁해결)", s["article"]))
    story.append(
        Paragraph(
            "본 계약과 관련하여 분쟁이 발생한 경우, 채권자 주소지를 관할하는 법원을 "
            "제1심 관할법원으로 한다.",
            s["clause"],
        )
    )

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "본 차용증은 2부를 작성하여 채권자와 채무자가 각 1부씩 보관한다.",
            s["center"],
        )
    )
    story.append(Paragraph("<b>2026년 7월 15일</b>", s["center"]))
    story.append(Spacer(1, 10))

    sign_data = [
        [
            Paragraph("채권자(대여인)", s["sign_label"]),
            Paragraph("채무자(차용인)", s["sign_label"]),
        ],
        [
            Paragraph(
                "성명: 조효정&nbsp;&nbsp;&nbsp;&nbsp;(인)<br/>"
                "주민등록번호: ____________________<br/>"
                "주소: ____________________________<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                "____________________________",
                s["sign_body"],
            ),
            Paragraph(
                "성명: 조효진&nbsp;&nbsp;&nbsp;&nbsp;(인)<br/>"
                "주민등록번호: ____________________<br/>"
                "주소: ____________________________<br/>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                "____________________________",
                s["sign_body"],
            ),
        ],
    ]
    sign_table = Table(sign_data, colWidths=[85 * mm, 85 * mm])
    sign_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 0.6, "#888888"),
                ("LINEBEFORE", (1, 0), (1, -1), 0.6, "#888888"),
                ("BACKGROUND", (0, 0), (-1, 0), "#F5F5F5"),
            ]
        )
    )
    story.append(sign_table)

    story.append(
        Paragraph(
            "※ 계좌이체 확인증 등 교부·이자 지급 증빙을 본 차용증과 함께 보관하시기 바랍니다.",
            s["footer"],
        )
    )

    doc.build(story)
    print(f"created: {OUT}")


if __name__ == "__main__":
    build()
