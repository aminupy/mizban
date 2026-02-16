package server

import (
	"strings"

	qrcode "github.com/skip2/go-qrcode"
)

func GenerateASCIIQR(data string) (string, error) {
	// Keep terminal QR small while still scannable for short LAN URLs.
	code, err := qrcode.New(data, qrcode.Low)
	if err != nil {
		return "", err
	}
	bitmap := code.Bitmap()
	const quietZone = 0

	totalHeight := len(bitmap) + (2 * quietZone)
	totalWidth := 0
	if len(bitmap) > 0 {
		totalWidth = len(bitmap[0]) + (2 * quietZone)
	}

	darkAt := func(y, x int) bool {
		y -= quietZone
		x -= quietZone
		if y < 0 || x < 0 || y >= len(bitmap) || x >= len(bitmap[y]) {
			return false
		}
		return bitmap[y][x]
	}

	var b strings.Builder
	for y := 0; y < totalHeight; y += 2 {
		for x := 0; x < totalWidth; x++ {
			top := darkAt(y, x)
			bottom := darkAt(y+1, x)
			switch {
			case top && bottom:
				b.WriteRune('█')
			case top:
				b.WriteRune('▀')
			case bottom:
				b.WriteRune('▄')
			default:
				b.WriteRune(' ')
			}
		}
		b.WriteByte('\n')
	}
	return b.String(), nil
}
