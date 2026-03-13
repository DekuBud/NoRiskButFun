# Purpose: Calculate a small placeholder quick score from the KPIs that were extracted.
from __future__ import annotations

from typing import Optional


def calculate_quick_score(
    turnover: Optional[float],
    ebit: Optional[float],
    ebitda: Optional[float],
    employees: Optional[int],
    investments: Optional[float],
) -> Optional[float]:
    """Return a simple score between 0 and 100 based on available KPI signals."""
    score = 50.0
    has_signal = False

    quickTest()

    if turnover is not None:
        has_signal = True
        score += 10 if turnover > 0 else -15

    if ebit is not None:
        has_signal = True
        score += 15 if ebit > 0 else -20

    if ebitda is not None:
        has_signal = True
        score += 15 if ebitda > 0 else -15

    if employees is not None:
        has_signal = True
        score += 5 if employees > 0 else -5

    if investments is not None:
        has_signal = True
        score += 5 if investments >= 0 else -5

    if not has_signal:
        return None

    # TODO: Replace this placeholder with a business-approved scoring model.
    return round(max(0.0, min(100.0, score)), 2)


def quickTest() -> dict[str, float]:
    # Dummy-Daten
    # Jahresüberschuss
    netprofit: float = -2109586.30
    # Abschreibung inkl. Teilwert-AfA
    depreciation: float = 87880.69
    # Rückstellungen für Abfertigungen aktuelles Jahr
    provisionsForSeverancePaymentsCurrent: float = 0
    # Rückstellungen für Abfertigungen letztes Jahr
    provisionsForSeverancePaymentsPast: float = 0
    # Rückstellungen für Pension aktuelles Jahr
    provisionsForPensionCurrent: float = 3449191.80
    # Rückstellungen für Pension letztes Jahr
    provisionsForPensionPast: float = 2961403.53
    # Buchwert abgegangener Anlagen
    bookValueOfDisposedAssets: float = 0
    # Eigenkapital
    equity: float = 151733151.61
    # Gesamtkapital
    totalCapital: float = 345260174.19
    # Flüssige Mittel
    cash: float = 328317.80
    # kurzfristige Wertpapiere
    stocks: float = 0
    # Ergebniss der gewöhnlichen Geschäftstätigkeit
    egt: float = -2098151.90
    # Fremdkapitalzinsen
    interestExpense: float = 7249174.73
    # Umsatz
    revenue: float = 6234414.24
    # Bestandsveränderung
    changeInInvertory: float = 0
    # Aktivierte Eigenleistungen
    capitalizedOwnWork: float = 0

    return dummyMethode(
        netprofit,
        depreciation,
        provisionsForSeverancePaymentsCurrent,
        provisionsForSeverancePaymentsPast,
        provisionsForPensionCurrent,
        provisionsForPensionPast,
        bookValueOfDisposedAssets,
        equity,
        totalCapital,
        cash,
        stocks,
        egt,
        interestExpense,
        revenue,
        changeInInvertory,
        capitalizedOwnWork
    )

def dummyMethode(
    netprofit: Optional[float],
    depreciation: Optional[float],
    provisionsForSeverancePaymentsCurrent: Optional[float],
    provisionsForSeverancePaymentsPast: Optional[float],
    provisionsForPensionCurrent: Optional[float],
    provisionsForPensionPast: Optional[float],
    bookValueOfDisposedAssets: Optional[float],
    equity: Optional[float],
    totalCapital: Optional[float],
    cash: Optional[float],
    stocks: Optional[float],
    egt: Optional[float],
    interestExpense: Optional[float],
    revenue: Optional[float],
    changeInInvertory: Optional[float],
    capitalizedOwnWork: Optional[float]
) -> dict[str, float]:
    # Kontrolle der Variablen Felder on sie None sind
    # Diese Werte werden auf 0 gesetzt, damit die Berechnungen trotzdem gemacht werden können
    provisionsForSeverancePaymentsCurrent = zero_if_none(provisionsForSeverancePaymentsCurrent)
    provisionsForSeverancePaymentsPast = zero_if_none(provisionsForSeverancePaymentsPast)
    provisionsForPensionCurrent = zero_if_none(provisionsForPensionCurrent)
    provisionsForPensionPast = zero_if_none(provisionsForPensionPast)
    bookValueOfDisposedAssets = zero_if_none(bookValueOfDisposedAssets)
    cash = zero_if_none(cash)
    stocks = zero_if_none(stocks)
    egt = zero_if_none(egt)
    changeInInvertory = zero_if_none(changeInInvertory)
    capitalizedOwnWork = zero_if_none(capitalizedOwnWork)

    # Fremdkapital
    liabilities: float = totalCapital - equity
    # Betriebsleistung
    operatingPerformance = revenue + changeInInvertory + capitalizedOwnWork
    # Cash Flow
    provisionSeverancePayment = provisionsForSeverancePaymentsCurrent - provisionsForSeverancePaymentsPast
    provisionPension = provisionsForPensionCurrent - provisionsForPensionPast
    cashflow = netprofit + depreciation + provisionSeverancePayment + provisionPension + bookValueOfDisposedAssets
    
    # Eigenkapitalquote
    equityRatio = equity / totalCapital * 100
    equityRatioScore = 5
    if equityRatio > 30:
        equityRatioScore = 1
    elif equityRatio > 20:
        equityRatioScore = 2
    elif equityRatio > 10:
        equityRatioScore = 3
    elif equityRatio >= 0:
        equityRatioScore = 4
    
    # Schuldentilgungsdauer
    if cashflow != 0:
        debtRepaymentPeriod = (liabilities - cash - stocks) / cashflow
        debtRepaymentPeriodScore = 5
        if debtRepaymentPeriod < 0:
            debtRepaymentPeriodScore = 5
        elif debtRepaymentPeriod < 3:
            debtRepaymentPeriodScore = 1
        elif debtRepaymentPeriod < 5:
            debtRepaymentPeriodScore = 2
        elif debtRepaymentPeriod < 12:
            debtRepaymentPeriodScore = 3
        elif debtRepaymentPeriod < 30:
            debtRepaymentPeriodScore = 4

    # Finanzielle Stabilität - Bewertung
    financialStability = (equityRatioScore + debtRepaymentPeriodScore) / 2

    # Gesamtkapitalrentablilität
    returnOnTotalAssets = (egt + interestExpense) / totalCapital * 100
    returnOnTotalAssetsScore = 5
    if returnOnTotalAssets > 15:
        returnOnTotalAssetsScore = 1
    elif returnOnTotalAssets > 12:
        returnOnTotalAssetsScore = 2
    elif returnOnTotalAssets > 8:
        returnOnTotalAssetsScore = 3
    elif returnOnTotalAssets >= 0:
        returnOnTotalAssetsScore = 4

    # Cash-FLow Leistungsrate
    cashFlowPerformanceRate = cashflow / operatingPerformance * 100
    cashFlowPerformanceRateScore = 5
    if cashFlowPerformanceRate > 10:
        cashFlowPerformanceRateScore = 1
    elif cashFlowPerformanceRate > 8:
        cashFlowPerformanceRateScore = 2
    elif cashFlowPerformanceRate > 5:
        cashFlowPerformanceRateScore = 3
    elif cashFlowPerformanceRate >= 0:
        cashFlowPerformanceRateScore = 4

    # Ertragskraft - Bewertung
    earningsPower = (returnOnTotalAssetsScore + cashFlowPerformanceRateScore) / 2

    # Gesamtbewertung
    quickScore = (financialStability + earningsPower) / 2

    return {
        "equityRatio": round(equityRatio, 2),
        "debtRepaymentPeriod": round(debtRepaymentPeriod, 2),
        "returnOnTotalAssets": round(returnOnTotalAssets, 2),
        "cashFlowPerformanceRate": round(cashFlowPerformanceRate, 2),
        "financialStability": financialStability,
        "earningsPower": earningsPower,
        "quickScore": quickScore
    }

def zero_if_none(value: Optional[float]) -> float:
    return 0 if value is None else value

def calculate_ROI(
    profit: Optional[float],
    revenue: Optional[float],
    totalCapital: Optional[float]
) -> Optional[float]:
    profitabilityOfSales = profit / revenue
    capitalTurnover = revenue / totalCapital

    return round(profitabilityOfSales * capitalTurnover * 100, 2)