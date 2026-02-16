//go:build windows

package server

import "syscall"

func setSocketOptionsBestEffort(fd uintptr) {
	h := syscall.Handle(fd)
	_ = syscall.SetsockoptInt(h, syscall.SOL_SOCKET, syscall.SO_RCVBUF, socketBufferSize)
	_ = syscall.SetsockoptInt(h, syscall.SOL_SOCKET, syscall.SO_SNDBUF, socketBufferSize)
	_ = syscall.SetsockoptInt(h, syscall.IPPROTO_TCP, syscall.TCP_NODELAY, 1)
}
