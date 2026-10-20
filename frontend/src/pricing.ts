// Decimal string parsing avoids accepting exponent notation or silently rounding input.
export function euroToCents(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized))
    throw new Error(
      "Bitte gib einen Eurobetrag mit höchstens zwei Nachkommastellen ein.",
    );
  const [whole, fractional = ""] = normalized.split(".");
  const cents = Number(whole) * 100 + Number(fractional.padEnd(2, "0"));
  if (!Number.isSafeInteger(cents) || cents > 1000000)
    throw new Error("Der Betrag muss zwischen 0 und 10.000 Euro liegen.");
  return cents;
}

export function suggestedPrice(
  hourlyRate: number | null | undefined,
  minutes: number,
) {
  if (hourlyRate == null) return 0;
  return Math.floor((hourlyRate * minutes + 30) / 60);
}
