SHELL := /bin/bash

APP_NAME := mizban
VERSION ?= 2.0.0
DIST_DIR := dist
PACKAGES_DIR := $(DIST_DIR)/packages
ARCHES ?= amd64 arm64

LDFLAGS := -s -w -X 'main.version=$(VERSION)'
GO_BUILD_FLAGS := -trimpath -buildvcs=false
PLATFORMS := windows/amd64 windows/arm64 darwin/amd64 darwin/arm64 linux/amd64 linux/arm64

.PHONY: build build-local test archive checksums package package-windows package-macos package-linux release clean upx

build:
	@set -euo pipefail; \
	for platform in $(PLATFORMS); do \
		os=$${platform%/*}; \
		arch=$${platform#*/}; \
		out_dir="$(DIST_DIR)/$${os}-$${arch}"; \
		mkdir -p "$$out_dir"; \
		bin_name="$(APP_NAME)"; \
		if [[ "$$os" == "windows" ]]; then bin_name="$$bin_name.exe"; fi; \
		echo "==> building $$os/$$arch"; \
		GOOS="$$os" GOARCH="$$arch" CGO_ENABLED=0 go build $(GO_BUILD_FLAGS) -ldflags "$(LDFLAGS)" -o "$$out_dir/$$bin_name" ./cmd/mizban; \
		rm -rf "$$out_dir/web"; \
		cp -R web "$$out_dir/web"; \
	done

build-local:
	@mkdir -p "$(DIST_DIR)/local"
	GOOS=$$(go env GOOS) GOARCH=$$(go env GOARCH) CGO_ENABLED=0 go build $(GO_BUILD_FLAGS) -ldflags "$(LDFLAGS)" -o "$(DIST_DIR)/local/$(APP_NAME)" ./cmd/mizban
	@rm -rf "$(DIST_DIR)/local/web"
	@cp -R web "$(DIST_DIR)/local/web"

test:
	go test ./...

archive: build
	@set -euo pipefail; \
	mkdir -p "$(PACKAGES_DIR)"; \
	for platform in $(PLATFORMS); do \
		os=$${platform%/*}; \
		arch=$${platform#*/}; \
		os_name="$$os"; \
		if [[ "$$os" == "darwin" ]]; then os_name="macos"; fi; \
		base="$(APP_NAME)-$(VERSION)-$${os_name}-$${arch}"; \
		echo "==> archiving $${os}/$${arch}"; \
		tar -C "$(DIST_DIR)" -czf "$(PACKAGES_DIR)/$${base}.tar.gz" "$${os}-$${arch}"; \
	done

checksums:
	@set -euo pipefail; \
	if [[ ! -d "$(PACKAGES_DIR)" ]]; then \
		echo "Missing $(PACKAGES_DIR). Run 'make archive' first."; \
		exit 1; \
	fi; \
	cd "$(PACKAGES_DIR)"; \
	sha256sum *.tar.gz > SHA256SUMS.txt; \
	echo "Wrote $(PACKAGES_DIR)/SHA256SUMS.txt"

package: package-windows package-macos package-linux

package-windows:
	@set -euo pipefail; \
	for arch in $(ARCHES); do \
		./packaging/windows/build_msi.sh "$(VERSION)" "$$arch"; \
	done

package-macos:
	@set -euo pipefail; \
	for arch in $(ARCHES); do \
		./packaging/macos/build_pkg.sh "$(VERSION)" "$$arch"; \
		./packaging/macos/build_dmg.sh "$(VERSION)" "$$arch"; \
	done

package-linux:
	@set -euo pipefail; \
	for arch in $(ARCHES); do \
		./packaging/linux/build_deb.sh "$(VERSION)" "$$arch"; \
	done

release: clean archive checksums

upx:
	@if ! command -v upx >/dev/null 2>&1; then \
		echo "upx is not installed"; \
		exit 1; \
	fi
	@find "$(DIST_DIR)" -type f \( -name 'mizban' -o -name 'mizban.exe' \) -print -exec upx --best --lzma {} \;

clean:
	rm -rf "$(DIST_DIR)"
