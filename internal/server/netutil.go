package server

import (
	"fmt"
	"net"
)

func ServerURL(port int) string {
	return fmt.Sprintf("http://%s:%d/", DetectLANIPv4(), port)
}

func DetectLANIPv4() string {
	ifaces, err := net.Interfaces()
	if err == nil {
		for _, iface := range ifaces {
			if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
				continue
			}
			addrs, err := iface.Addrs()
			if err != nil {
				continue
			}
			for _, addr := range addrs {
				var ip net.IP
				switch t := addr.(type) {
				case *net.IPNet:
					ip = t.IP
				case *net.IPAddr:
					ip = t.IP
				}
				if ip == nil {
					continue
				}
				if v4 := ip.To4(); v4 != nil && !v4.IsLoopback() {
					return v4.String()
				}
			}
		}
	}

	conn, err := net.Dial("udp4", "10.255.255.255:1")
	if err == nil {
		defer conn.Close()
		if udpAddr, ok := conn.LocalAddr().(*net.UDPAddr); ok {
			if ip := udpAddr.IP.To4(); ip != nil {
				return ip.String()
			}
		}
	}

	return "127.0.0.1"
}
