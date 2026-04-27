"""Google Sheets layout construction — builds section data, no API calls."""

import re
from datetime import datetime

TXN_ROW = 39  # first data row of the transaction log (1-indexed)
T = TXN_ROW   # shorthand used inside build_sections formulas


def date_to_formula(exp_str):
    """'MM/DD/YYYY' → 'DATE(YYYY,MM,DD)'"""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", exp_str or "")
    if not m:
        return "DATE(2099,1,1)"
    return f"DATE({m.group(3)},{int(m.group(1))},{int(m.group(2))})"


def shorten_symbol(symbol):
    """'NVDA 01/16/2026 150.00 C' → '150C 01/16/26'"""
    m = re.match(r"\S+\s+(\d{2}/\d{2})/(\d{4})\s+([\d.]+)\s+([CP])", symbol)
    if not m:
        return symbol
    strike = m.group(3).rstrip("0").rstrip(".")
    typ = "C" if m.group(4) == "C" else "P"
    return f"{strike}{typ} {m.group(1)}/{m.group(2)[2:]}"


def build_sections(ticker, open_positions, last_row, avg_held_anchor=None,
                   brokerage="", status="Consistent", closed_avg_days=None):
    """Return a dict of {range_str: 2d_array} for all calculated sections."""

    L = last_row  # last transaction row — bound SUMPRODUCT ranges here so
                  # footnote text below the log can't poison DAYS()/DATEVALUE

    if status == "Closed" and closed_avg_days is not None:
        avg_days_formula = str(closed_avg_days)
    elif avg_held_anchor:
        y, mo, d = avg_held_anchor
        avg_days_formula = f"=TODAY()-DATE({y},{mo},{d})"
    else:
        avg_days_formula = "0"

    open_calls = [p for p in open_positions if p["type"] == "Call"]
    open_puts_list = [p for p in open_positions if p["type"] == "Put"]

    itm = open_calls[0] if open_calls else None
    if itm:
        itm_strike = itm["strike"]
        itm_exp = itm["expiration"]
        itm_date_f = date_to_formula(itm_exp)
        oc_strike = itm["strike"]
        oc_exp = itm["expiration"]
        oc_cts = -itm["contracts"]
        oc_prem = round(itm["premium"], 2)
        oc_df = date_to_formula(itm["expiration"])
        oc_status = f"=IF(B5>{itm_strike},\"ITM\",\"OTM\")"
    else:
        itm_strike = ""
        itm_exp = ""
        itm_date_f = "DATE(2099,1,1)"
        oc_strike = oc_exp = oc_cts = oc_prem = ""
        oc_df = itm_date_f
        oc_status = ""

    op = open_puts_list[0] if open_puts_list else None
    if op:
        op_strike = op["strike"]
        op_exp = op["expiration"]
        op_cts = -op["contracts"]
        op_prem = round(op["premium"], 2)
        op_df = date_to_formula(op["expiration"])
        op_status = f"=IF(B5<{op_strike},\"ITM\",\"OTM\")"
    else:
        op_strike = op_exp = op_cts = op_prem = ""
        op_df = "DATE(2099,1,1)"
        op_status = ""

    return {
        "A1:C1": [[ticker, "Status", status]],

        "A3:B8": [
            ["CURRENT VALUES", ""],
            ["Last Updated", datetime.now().strftime("%m/%d/%y %H:%M")],
            ["Stock Price", ""],
            ["** Adj Cost Basis / Share", f"=IFERROR(-SUM(J${T}:J${L})/E4,0)"],
            ["Calls Market Value", ""],
            ["Puts Market Value", ""],
        ],

        "D3:E7": [
            ["STOCK POSITION", ""],
            ["Shares Held",
             f"=SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*G${T}:G${L})"
             f"-SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Sell\")*G${T}:G${L})"],
            ["Avg Cost / Share",
             f"=IFERROR(-(SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*J${T}:J${L})+SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Sell\")*J${T}:J${L}))/E4,0)"],
            ["Market Value", "=E4*B5"],
            ["Total Invested",
             f"=IF(E4=0,0,SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*J${T}:J${L})+SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Sell\")*J${T}:J${L}))"],
        ],

        "G3:H8": [
            ["STOCK RESULTS", ""],
            ["Gain $",
             f"=IF(E4=0,"
             f"SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*J${T}:J${L})+SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Sell\")*J${T}:J${L}),"
             f"E6+E7)"],
            ["Gain %", f"=IFERROR(-H4/SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*J${T}:J${L}),0)"],
            ["Days Since First Purchase",
             f"=IF(COUNTIFS(C${T}:C${L},\"Stock\",B${T}:B${L},\"Buy\")>0,DAYS(TODAY(),MINIFS(A${T}:A${L},C${T}:C${L},\"Stock\",B${T}:B${L},\"Buy\")),\"\")"],
            ["Avg Days Held", avg_days_formula],
            ["Ann Gain %", "=IFERROR(H5*(365/H7),0)"],
        ],

        "A10:B15": [
            ["CALL HISTORY STATS", ""],
            ["Call Premium Received",
             f"=SUMPRODUCT((C${T}:C${L}=\"Call\")*(J${T}:J${L}>0)*J${T}:J${L})"],
            ["Call Premium Paid",
             f"=SUMPRODUCT((C${T}:C${L}=\"Call\")*(J${T}:J${L}<0)*J${T}:J${L})"],
            ["Net Call Premium (all time)",
             f"=SUMPRODUCT((C${T}:C${L}=\"Call\")*J${T}:J${L})"],
            ["Calls Market Value", "=B7"],
            ["Covered Call Results", "=B13+B14"],
        ],

        "D10:E15": [
            ["OPEN CALLS", ""],
            ["Strike", oc_strike],
            ["Expiration", oc_exp],
            ["Days Left", f"=DAYS({oc_df},TODAY())" if itm else ""],
            ["Contracts", oc_cts],
            ["Status", oc_status],
        ],

        "G10:H16": [
            ["OPEN CALL METRICS", ""],
            ["Premium Received", oc_prem],
            ["Cost to Close", "=B7" if itm else ""],
            ["Unrealized P&L", "=H11+H12" if itm else ""],
            ["Intrinsic Value", f"=MAX(0,B5-{itm_strike})*E14*100" if itm_strike != "" else ""],
            ["Time Value", "=H12-H14" if itm else ""],
            ["** TV Ann Yield", "=IFERROR(MAX(0,-H15)/(-E14*100*B5+B7)*(365/E13),0)" if itm else ""],
        ],

        "A18:B23": [
            ["PUT HISTORY STATS", ""],
            ["Put Premium Received",
             f"=SUMPRODUCT((C${T}:C${L}=\"Put\")*(J${T}:J${L}>0)*J${T}:J${L})"],
            ["Put Premium Paid",
             f"=SUMPRODUCT((C${T}:C${L}=\"Put\")*(J${T}:J${L}<0)*J${T}:J${L})"],
            ["Net Put Premium (all time)",
             f"=SUMPRODUCT((C${T}:C${L}=\"Put\")*J${T}:J${L})"],
            ["Puts Market Value", "=B8"],
            ["Put Results", "=B21+B22"],
        ],

        "D18:E23": [
            ["OPEN PUTS", ""],
            ["Strike", op_strike],
            ["Expiration", op_exp],
            ["Days Left", f"=DAYS({op_df},TODAY())" if op else ""],
            ["Contracts", op_cts],
            ["Status", op_status],
        ],

        "G18:H24": [
            ["OPEN PUTS METRICS", ""],
            ["Premium Received", op_prem],
            ["Cost to Close", "=B8" if op else ""],
            ["Unrealized P&L", "=H19+H20" if op else ""],
            ["Intrinsic Value", f"=MAX(0,{op_strike}-B5)*E22*100" if op else ""],
            ["Time Value", "=H20-H22" if op else ""],
            ["TV Ann Yield", "=IFERROR(IF(E21>0,MAX(0,-H23)/(-E22*100*E19)*(365/E21),0),0)" if op else ""],
        ],

        "A26:B30": [
            ["INCOME", ""],
            ["Total Dividends", f"=SUMPRODUCT((C${T}:C${L}=\"Dividend\")*J${T}:J${L})"],
            ["Dividend Count", f"=COUNTIF(C${T}:C${L},\"Dividend\")"],
            ["Net Call Premium (all time)", "=B13"],
            ["Net Put Premium (all time)", "=B21"],
        ],

        "D26:E31": [
            ["P&L BREAKDOWN", ""],
            ["Stock Gain", "=H4"],
            ["Covered Call Results", "=B15"],
            ["Put Results", "=B23"],
            ["Dividends", "=B27"],
            ["Total P&L", "=E27+E28+E29+E30"],
        ],

        "G26:H29": [
            ["RETURNS", ""],
            ["Close-out Value",
             f"=SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Sell\")*J${T}:J${L})"
             if status == "Closed" else "=E6+B7+B8"],
            ["Ann Yield on Invested Capital",
             f"=IFERROR(E31/(-SUMPRODUCT((C${T}:C${L}=\"Stock\")*(B${T}:B${L}=\"Buy\")*J${T}:J${L}))*(365/H7),0)"
             if status == "Closed" else "=IFERROR(-E31/E7*(365/H7),0)"],
            ["Ann Yield on Close-out Value", "=IFERROR(E31/H27*(365/H7),0)"],
        ],

        f"A{TXN_ROW-2}:K{TXN_ROW-1}": [
            ["TRANSACTION LOG", "", "", "", "", "", "", "", "", "", ""],
            ["Date", "Action", "Type", "Symbol", "Strike", "Expiration",
             "Qty", "Price", "Fees", "Net Amount", "Notes"],
        ],
    }
