# -*- coding: utf-8 -*-
"""토스증권 Open API 클라이언트.

공식 문서: https://developers.tossinvest.com/docs
OpenAPI: https://openapi.tossinvest.com/openapi-docs/latest/openapi.json
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://openapi.tossinvest.com"

# 한글 종목명 검색용 KRX 마스터 (세션당 1회 로드)
_KRX_LISTING_CACHE: Any = None


class TossInvestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _load_krx_listing():
    """KRX 전 종목 마스터 (FinanceDataReader)."""
    global _KRX_LISTING_CACHE
    if _KRX_LISTING_CACHE is not None:
        return _KRX_LISTING_CACHE
    try:
        import FinanceDataReader as fdr
    except ImportError as e:
        raise TossInvestError(
            "한글 종목명 검색은 finance-datareader 가 필요합니다:\n"
            "  pip install finance-datareader"
        ) from e
    listing = fdr.StockListing("KRX")
    if listing is None or listing.empty:
        raise TossInvestError("KRX 종목 목록을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
    _KRX_LISTING_CACHE = listing
    return _KRX_LISTING_CACHE


class TossInvestClient:
  """OAuth2 Client Credentials + REST 호출 래퍼."""

  def __init__(
      self,
      client_id: str,
      client_secret: str,
      account_seq: int | None = None,
      base_url: str = DEFAULT_BASE_URL,
      max_retries: int = 3,
  ):
      self.client_id = client_id
      self.client_secret = client_secret
      self.account_seq = account_seq
      self.base_url = base_url.rstrip("/")
      self.max_retries = max_retries
      self._token: str | None = None
      self._token_expires_at = 0.0

  @classmethod
  def from_env(cls) -> "TossInvestClient":
      client_id = os.getenv("TOSSINVEST_CLIENT_ID", "").strip()
      client_secret = os.getenv("TOSSINVEST_CLIENT_SECRET", "").strip()
      if not client_id or not client_secret:
          raise TossInvestError(
              ".env 파일이 없거나 키가 비어 있습니다.\n"
              "  1) copy .env.example .env\n"
              "  2) WTS > 설정 > Open API 에서 발급한 client_id / client_secret 입력"
          )
      if "your_client" in client_id or "your_client" in client_secret:
          raise TossInvestError(
              ".env 에 예시 값이 그대로 있습니다. 실제 client_id / client_secret 으로 바꿔 주세요."
          )
      seq_raw = os.getenv("TOSSINVEST_ACCOUNT_SEQ", "").strip()
      account_seq = int(seq_raw) if seq_raw else None
      base_url = os.getenv("TOSSINVEST_API_BASE_URL", DEFAULT_BASE_URL)
      return cls(client_id, client_secret, account_seq, base_url)

  # ── Auth ──
  def _issue_token(self) -> None:
      url = f"{self.base_url}/oauth2/token"
      data = {
          "grant_type": "client_credentials",
          "client_id": self.client_id,
          "client_secret": self.client_secret,
      }
      resp = requests.post(url, data=data, timeout=30)
      if resp.status_code != 200:
          raise TossInvestError(
              f"토큰 발급 실패 ({resp.status_code}): {resp.text[:300]}",
              resp.status_code,
              resp.text,
          )
      body = resp.json()
      self._token = body["access_token"]
      expires_in = int(body.get("expires_in", 86400))
      self._token_expires_at = time.time() + max(expires_in - 60, 60)

  def _get_token(self) -> str:
      if not self._token or time.time() >= self._token_expires_at:
          self._issue_token()
      return self._token  # type: ignore[return-value]

  # ── HTTP ──
  def _request(
      self,
      method: str,
      path: str,
      *,
      params: dict | None = None,
      json_body: dict | None = None,
      need_account: bool = False,
      account_seq: int | None = None,
  ) -> Any:
      headers = {"Authorization": f"Bearer {self._get_token()}"}
      if need_account:
          seq = account_seq if account_seq is not None else self.account_seq
          if seq is None:
              accounts = self.get_accounts()
              if not accounts:
                  raise TossInvestError("등록된 계좌가 없습니다.")
              seq = accounts[0]["accountSeq"]
              self.account_seq = seq
          headers["X-Tossinvest-Account"] = str(seq)

      url = f"{self.base_url}{path}"
      last_err: Exception | None = None
      for attempt in range(self.max_retries):
          resp = requests.request(
              method, url, headers=headers, params=params, json=json_body, timeout=30
          )
          if resp.status_code == 401 and attempt == 0:
              self._token = None
              headers["Authorization"] = f"Bearer {self._get_token()}"
              continue
          if resp.status_code == 429:
              wait = float(resp.headers.get("Retry-After", 1 + attempt))
              time.sleep(wait)
              last_err = TossInvestError("Rate limit 초과", 429, resp.text)
              continue
          if resp.status_code >= 400:
              try:
                  payload = resp.json()
                  msg = payload.get("error", {}).get("message", resp.text)
              except Exception:
                  payload = resp.text
                  msg = resp.text[:300]
              raise TossInvestError(f"API 오류 ({resp.status_code}): {msg}", resp.status_code, payload)
          if resp.status_code == 204 or not resp.content:
              return None
          body = resp.json()
          return body.get("result", body)
      raise last_err or TossInvestError("요청 실패")

  # ── Account / Asset ──
  def get_accounts(self) -> list[dict]:
      """GET /api/v1/accounts — 계좌 목록."""
      return self._request("GET", "/api/v1/accounts") or []

  def get_holdings(self, account_seq: int | None = None, symbol: str | None = None) -> dict:
      """GET /api/v1/holdings — 보유 종목."""
      params = {"symbol": symbol} if symbol else None
      return self._request(
          "GET", "/api/v1/holdings", params=params, need_account=True, account_seq=account_seq
      )

  def get_buying_power(
      self, account_seq: int | None = None, currency: str = "KRW"
  ) -> dict:
      """GET /api/v1/buying-power — 매수 가능 금액 (currency: KRW | USD)."""
      currency = currency.upper()
      if currency not in ("KRW", "USD"):
          raise TossInvestError("currency 는 KRW 또는 USD 여야 합니다.")
      return self._request(
          "GET",
          "/api/v1/buying-power",
          params={"currency": currency},
          need_account=True,
          account_seq=account_seq,
      )

  # ── Stock / Market ──
  def get_stocks(self, symbols: list[str]) -> list[dict]:
      """GET /api/v1/stocks — 종목 기본정보 (심볼 조회)."""
      if not symbols:
          return []
      sym = ",".join(symbols[:200])
      return self._request("GET", "/api/v1/stocks", params={"symbols": sym}) or []

  def get_prices(self, symbols: list[str]) -> list[dict]:
      """GET /api/v1/prices — 현재가."""
      if not symbols:
          return []
      sym = ",".join(symbols[:200])
      return self._request("GET", "/api/v1/prices", params={"symbols": sym}) or []

  # ── Order ──
  def create_order(
      self,
      symbol: str,
      side: str,
      quantity: int,
      *,
      order_type: str = "MARKET",
      price: float | None = None,
      client_order_id: str | None = None,
      confirm_high_value: bool = False,
      account_seq: int | None = None,
  ) -> dict:
      """POST /api/v1/orders — 주문 생성."""
      if quantity <= 0:
          raise TossInvestError("주문 수량은 1주 이상이어야 합니다.")
      side = side.upper()
      order_type = order_type.upper()
      if side not in ("BUY", "SELL"):
          raise TossInvestError("side 는 BUY 또는 SELL 이어야 합니다.")
      if order_type not in ("LIMIT", "MARKET"):
          raise TossInvestError("order_type 은 LIMIT 또는 MARKET 이어야 합니다.")

      body: dict[str, Any] = {
          "symbol": str(symbol).zfill(6) if str(symbol).isdigit() else symbol.upper(),
          "side": side,
          "orderType": order_type,
          "quantity": str(quantity),
      }
      if order_type == "LIMIT":
          if price is None:
              raise TossInvestError("지정가 주문에는 price 가 필요합니다.")
          body["price"] = str(int(price)) if str(symbol).isdigit() else str(price)
      if client_order_id:
          body["clientOrderId"] = client_order_id
      if confirm_high_value:
          body["confirmHighValueOrder"] = True

      return self._request(
          "POST",
          "/api/v1/orders",
          json_body=body,
          need_account=True,
          account_seq=account_seq,
      )

  def cancel_order(self, order_id: str, account_seq: int | None = None) -> dict:
      """POST /api/v1/orders/{orderId}/cancel — 주문 취소."""
      return self._request(
          "POST",
          f"/api/v1/orders/{order_id}/cancel",
          need_account=True,
          account_seq=account_seq,
      )

  def get_orders(
      self,
      status: str,
      *,
      symbol: str | None = None,
      account_seq: int | None = None,
  ) -> dict:
      """GET /api/v1/orders — 주문 목록 (status: OPEN | CLOSED)."""
      params: dict[str, str] = {"status": status.upper()}
      if symbol:
          params["symbol"] = symbol
      return self._request(
          "GET",
          "/api/v1/orders",
          params=params,
          need_account=True,
          account_seq=account_seq,
      ) or {"orders": []}

  def get_sellable_quantity(self, symbol: str, account_seq: int | None = None) -> dict:
      """GET /api/v1/sellable-quantity — 매도 가능 수량."""
      sym = str(symbol).zfill(6) if str(symbol).isdigit() else symbol.upper()
      return self._request(
          "GET",
          "/api/v1/sellable-quantity",
          params={"symbol": sym},
          need_account=True,
          account_seq=account_seq,
      )

  def search_by_symbol(self, query: str) -> list[dict]:
      """심볼(티커)로 종목 정보 + 현재가 조회."""
      symbol = query.strip().upper()
      if symbol.isdigit():
          symbol = symbol.zfill(6)
      stocks = self.get_stocks([symbol])
      if not stocks:
          return []
      prices = {p.get("symbol"): p for p in self.get_prices([symbol])}
      out = []
      for s in stocks:
          px = prices.get(s.get("symbol"), {})
          chg = px.get("changeRate")
          out.append({
              "symbol": s.get("symbol"),
              "name": s.get("name"),
              "englishName": s.get("englishName"),
              "market": s.get("market"),
              "currency": s.get("currency"),
              "status": s.get("status"),
              "price": px.get("lastPrice"),
              "changeRate": f"{float(chg)*100:.2f}" if chg not in (None, "") else None,
          })
      return out

  def search_by_name_local(self, name_query: str) -> list[dict]:
      """한글 종목명 검색 (FinanceDataReader — 공식 API에 이름검색 없음)."""
      listing = _load_krx_listing()
      name_q = name_query.strip()
      if not name_q:
          return []

      names = listing["Name"].astype(str)
      exact = listing[names == name_q]
      partial = listing[names.str.contains(name_q, na=False, regex=False)]

      symbols: list[str] = []
      for code in exact["Code"].tolist():
          symbols.append(str(code).zfill(6))
      for code in partial["Code"].tolist():
          sym = str(code).zfill(6)
          if sym not in symbols:
              symbols.append(sym)
          if len(symbols) >= 20:
              break
      if not symbols:
          return []
      return self.search_by_symbols_bulk(symbols[:10])

  def search_by_symbols_bulk(self, symbols: list[str]) -> list[dict]:
      stocks = self.get_stocks(symbols)
      stock_map = {s.get("symbol"): s for s in stocks}
      prices = {p.get("symbol"): p for p in self.get_prices(symbols)}
      rows = []
      for sym in symbols:
          s = stock_map.get(sym)
          if not s:
              continue
          px = prices.get(sym, {})
          chg = px.get("changeRate")
          rows.append({
              "symbol": sym,
              "name": s.get("name"),
              "market": s.get("market"),
              "currency": s.get("currency"),
              "price": px.get("lastPrice"),
              "changeRate": f"{float(chg)*100:.2f}" if chg not in (None, "") else None,
          })
      return rows

  def search(self, query: str) -> list[dict]:
      """심볼 또는 한글 종목명 검색."""
      q = query.strip()
      if not q:
          return []
      if q.isdigit() or (q.replace(".", "").replace("-", "").isalnum() and q.isascii()):
          return self.search_by_symbol(q)
      return self.search_by_name_local(q)
