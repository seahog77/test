#!/usr/bin/env python3
"""가우시안 방송채널(BC)의 dirty paper coding(DPC) 용량.

참고 논문
---------
Wei Yu and John M. Cioffi, "Sum Capacity of Gaussian Vector Broadcast Channels,"
IEEE Transactions on Information Theory, vol. 50, no. 9, pp. 1875-1892, Sep. 2004.

논문은 실수 채널을 다루며 용량을 자연로그(nats)로 적는다.
  C = max_{Sxx} min_{Szz}  (1/2) ln |H Sxx H^T + Szz| / |Szz|
이 프로그램은 같은 양을 bits로 보고한다. 즉 (1/2) log2(...).

사용자별 DPC 전송률은 간섭을 송신측에서 미리 뺀 뒤의 SINR만으로 결정된다
(Costa의 writing on dirty paper를 BC에 적용한 논문 식 (4), Theorem 1).

  R_i = (1/2) log2(1 + SINR_i)

스칼라 열화 BC (식 (4), σ1 < σ2, P1 = αP, P2 = (1-α)P):
  SINR_1 = P1 / σ1²                  # 약사용자 신호를 DPC로 제거
  SINR_2 = P2 / (σ2² + P1)           # 강사용자 신호는 잡음으로 남음

벡터 BC 합용량 (Theorem 3)은 논문이 동시에 인용한 MAC-BC 쌍대성으로 계산한다.
단일 안테나 사용자 K명, 송신 안테나 Nt개, 채널 행벡터 h_i 일 때

  C = max_{q_i ≥ 0, Σ q_i ≤ P}
        (1/2) log2 det( I + (1/σ²) Σ_i q_i h_i h_i^T )

부록의 3×3 예제 (P = 5)에서 이 값이 논문의 안장점 값 2.8952 nats 와 일치한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
from scipy.optimize import minimize

PAPER_APPENDIX_NATS = 2.8952

# 부록 식 (118). 행이 서로 협력하지 않는 수신기 y1, y2, y3.
PAPER_CHANNEL = np.array(
    [
        [1.0, -0.3, 0.2],
        [-0.4, 2.0, 0.5],
        [-0.1, 0.2, 3.0],
    ],
    dtype=float,
)


def dpc_rate_from_sinr(sinr: np.ndarray | float) -> np.ndarray | float:
    """DPC 후 사용자 전송률. R = (1/2) log2(1 + SINR). 단위는 bits/실수 차원."""
    return 0.5 * np.log2(1.0 + np.asarray(sinr, dtype=float))


def scalar_bc_sinrs(
    sinr_db: np.ndarray,
    alpha: float,
    sigma2_over_sigma1: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """스칼라 열화 BC의 SINR.

    기준 SINR은 P/σ1² 이다. 사용자 1이 더 깨끗한 채널(σ1² < σ2²)이다.
    DPC 순서: 약사용자(2)를 먼저 부호화하고, 강사용자(1)는 그 신호를
    비인과적으로 알고 dirty-paper 부호화한다 (논문 식 (4)).
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha는 0과 1 사이여야 합니다.")
    if sigma2_over_sigma1 <= 1.0:
        raise ValueError("열화 BC는 σ2²/σ1² > 1 이어야 합니다.")

    sinr = 10.0 ** (np.asarray(sinr_db, dtype=float) / 10.0)  # P/σ1²
    p1 = alpha * sinr
    p2 = (1.0 - alpha) * sinr
    sinr1 = p1  # σ1² = 1 로 정규화
    sinr2 = p2 / (sigma2_over_sigma1 + p1)
    # DPC를 쓰지 않으면 강사용자도 약사용자 전력을 잡음으로 본다.
    sinr1_tin = p1 / (1.0 + p2)
    return sinr1, sinr2, sinr1_tin


def _mac_sum_rate_and_grad(
    H: np.ndarray, q: np.ndarray, noise: float
) -> tuple[float, np.ndarray]:
    """쌍대 MAC 합전송률(bits)과 q에 대한 기울기."""
    k_users, n_tx = H.shape
    cov = noise * np.eye(n_tx)
    for i in range(k_users):
        if q[i] != 0.0:
            cov += q[i] * np.outer(H[i], H[i])
    chol = np.linalg.cholesky(cov)
    logdet = 2.0 * np.sum(np.log(np.diag(chol)))
    solved = np.linalg.solve(cov, H.T)  # R^{-1} h_i 를 열로
    quad = np.sum(H.T * solved, axis=0)  # h_i^T R^{-1} h_i
    nats = 0.5 * (logdet - n_tx * np.log(noise))
    bits = nats / np.log(2.0)
    grad_bits = (0.5 * quad) / np.log(2.0)
    return float(bits), grad_bits


def dpc_sum_capacity(
    H: np.ndarray, power: float, noise: float = 1.0
) -> tuple[float, np.ndarray]:
    """벡터 BC의 DPC 합용량(bits)과 쌍대 MAC 전력 q.

    H의 각 행은 단일 안테나 사용자의 실수 채널이다.
    합전송률은 q에 대해 오목이므로 합전력 제약의 최적값은 전역 최적이다.
    """
    channel = np.atleast_2d(np.asarray(H, dtype=float))
    k_users, _n_tx = channel.shape
    if power < 0.0:
        raise ValueError("전력 P는 0 이상이어야 합니다.")
    if power == 0.0 or k_users == 0:
        return 0.0, np.zeros(k_users)

    def objective(q: np.ndarray) -> tuple[float, np.ndarray]:
        rate, grad = _mac_sum_rate_and_grad(channel, q, noise)
        return -rate, -grad

    constraint = {"type": "ineq", "fun": lambda q: power - np.sum(q)}
    bounds = [(0.0, power)] * k_users
    starts = [np.full(k_users, power / k_users)]
    gains = np.sum(channel * channel, axis=1)
    best_user = np.zeros(k_users)
    best_user[int(np.argmax(gains))] = power
    starts.append(best_user)

    best_rate = -np.inf
    best_q = starts[0]
    for q0 in starts:
        result = minimize(
            objective,
            q0,
            jac=True,
            bounds=bounds,
            constraints=constraint,
            method="SLSQP",
            tol=1e-14,
            options={"maxiter": 400, "ftol": 1e-14, "disp": False},
        )
        q_hat = np.clip(result.x, 0.0, None)
        total = float(np.sum(q_hat))
        if total > power and total > 0.0:
            q_hat *= power / total
        rate, _grad = _mac_sum_rate_and_grad(channel, q_hat, noise)
        if rate > best_rate:
            best_rate = rate
            best_q = q_hat
    return best_rate, best_q


def mac_sic_sinr(
    H: np.ndarray, q: np.ndarray, noise: float = 1.0, order: np.ndarray | None = None
) -> np.ndarray:
    """쌍대 MAC의 순차 간섭 제거 SINR.

    order의 앞쪽 사용자를 먼저 복호한다. 먼저 복호하는 사용자는
    아직 빼지 않은 사용자 신호를 간섭으로 본다.
    BC에서 이 전송률을 얻는 DPC 부호화 순서는 그 반대이다.
    """
    channel = np.atleast_2d(np.asarray(H, dtype=float))
    k_users, n_tx = channel.shape
    if order is None:
        order = np.arange(k_users)
    sinr = np.zeros(k_users)
    for step, user in enumerate(order):
        cov = noise * np.eye(n_tx)
        for other in order[step + 1 :]:
            cov += q[other] * np.outer(channel[other], channel[other])
        solved = np.linalg.solve(cov, channel[user])
        sinr[user] = float(q[user] * (channel[user] @ solved))
    return sinr


def zf_sum_rate(H: np.ndarray, power: float, noise: float = 1.0) -> float:
    """제로포싱 빔포밍 후 스칼라 채널에 물 채우기를 한 합전송률(bits)."""
    channel = np.atleast_2d(np.asarray(H, dtype=float))
    k_users, n_tx = channel.shape
    if k_users > n_tx:
        raise ValueError("ZF는 사용자 수가 송신 안테나 수 이하일 때 계산합니다.")
    precoder = np.linalg.pinv(channel)  # Nt x K, 열은 비정규 빔
    column_norm = np.linalg.norm(precoder, axis=0)
    # H W 가 대각이고, 정규화 후 이득 제곱은 1/||w_k||²
    gains = 1.0 / (column_norm**2)
    powers = _waterfill(gains, power, noise)
    sinr = powers * gains / noise
    return float(np.sum(dpc_rate_from_sinr(sinr)))


def tdma_rates(H: np.ndarray, power: float, noise: float = 1.0) -> tuple[float, float]:
    """균등 시간 TDMA 합전송률과, 최강 사용자에게만 보내는 전송률."""
    channel = np.atleast_2d(np.asarray(H, dtype=float))
    gains = np.sum(channel * channel, axis=1)
    single = dpc_rate_from_sinr(power * gains / noise)
    equal_time = float(np.mean(single))
    best_user = float(np.max(single))
    return equal_time, best_user


def _waterfill(gains: np.ndarray, power: float, noise: float) -> np.ndarray:
    """실수 병렬 채널 p_i = max(0, μ - noise/gain_i), Σ p_i = P."""
    gains = np.asarray(gains, dtype=float)
    if power <= 0.0:
        return np.zeros_like(gains)
    low = 0.0
    high = power + float(np.max(noise / gains)) + 1.0
    for _ in range(80):
        level = 0.5 * (low + high)
        allocated = np.maximum(0.0, level - noise / gains)
        if float(np.sum(allocated)) > power:
            high = level
        else:
            low = level
    allocated = np.maximum(0.0, low - noise / gains)
    total = float(np.sum(allocated))
    if total > 0.0 and abs(total - power) > 1e-8 * max(power, 1.0):
        allocated *= power / total
    return allocated


def verify_paper_appendix(tol_nats: float = 2e-4) -> float:
    """부록 식 (122): P = 5 일 때 합용량 2.8952 nats."""
    power = 5.0
    bits, q = dpc_sum_capacity(PAPER_CHANNEL, power, noise=1.0)
    nats = bits * np.log(2.0)
    if abs(nats - PAPER_APPENDIX_NATS) > tol_nats:
        raise AssertionError(
            f"부록 합용량이 논문 값과 다릅니다: {nats:.6f} nats "
            f"(논문 {PAPER_APPENDIX_NATS} nats), q={q}"
        )
    sinr = mac_sic_sinr(PAPER_CHANNEL, q, noise=1.0)
    summed = float(np.sum(dpc_rate_from_sinr(sinr)))
    if abs(summed - bits) > 1e-8:
        raise AssertionError(
            f"사용자 SINR 합전송률 {summed:.8f} 이 행렬식 합용량 {bits:.8f} 과 다릅니다."
        )
    return nats


def _korean_font() -> None:
    path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if Path(path).is_file():
        font_manager.fontManager.addfont(path)
        family = font_manager.FontProperties(fname=path).get_name()
        plt.rcParams["font.family"] = family
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["mathtext.fontset"] = "dejavusans"


def plot_capacity_vs_sinr(
    out_path: Path,
    alpha: float = 0.5,
    sigma2_over_sigma1: float = 4.0,
    sinr_min_db: float = -10.0,
    sinr_max_db: float = 30.0,
    n_points: int = 81,
) -> Path:
    """SINR(가로) 대 DPC capacity(세로) 그림 두 장을 한 파일에 저장한다."""
    _korean_font()
    sinr_db = np.linspace(sinr_min_db, sinr_max_db, n_points)

    sinr1, sinr2, sinr1_tin = scalar_bc_sinrs(sinr_db, alpha, sigma2_over_sigma1)
    rate1 = dpc_rate_from_sinr(sinr1)
    rate2 = dpc_rate_from_sinr(sinr2)
    sum_dpc = rate1 + rate2
    sum_tin = dpc_rate_from_sinr(sinr1_tin) + rate2
    sum_capacity = dpc_rate_from_sinr(10.0 ** (sinr_db / 10.0))

    vector_dpc = np.empty_like(sinr_db)
    vector_zf = np.empty_like(sinr_db)
    vector_tdma = np.empty_like(sinr_db)
    vector_best = np.empty_like(sinr_db)
    for index, value_db in enumerate(sinr_db):
        power = 10.0 ** (float(value_db) / 10.0)  # σ² = 1
        vector_dpc[index], _q = dpc_sum_capacity(PAPER_CHANNEL, power)
        vector_zf[index] = zf_sum_rate(PAPER_CHANNEL, power)
        vector_tdma[index], vector_best[index] = tdma_rates(PAPER_CHANNEL, power)

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.15), constrained_layout=True)
    blue, orange, green, purple = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")

    left = axes[0]
    left.plot(sinr_db, sum_dpc, color=blue, lw=2.2, zorder=2, label=r"DPC 합  $R_1+R_2$")
    left.plot(
        sinr_db,
        sum_capacity,
        color="#222222",
        lw=1.7,
        ls=(0, (4, 2)),
        zorder=3,
        label=r"합용량  $\frac{1}{2}\log_2(1+\mathrm{SINR})$",
    )
    left.plot(sinr_db, rate1, color=blue, lw=1.6, ls="--", label=r"DPC  $R_1$ (강사용자)")
    left.plot(sinr_db, rate2, color=green, lw=1.6, ls="--", label=r"DPC  $R_2$ (약사용자)")
    left.plot(sinr_db, sum_tin, color=orange, lw=2.0, label="간섭을 잡음으로 처리 (합)")
    left.set_title(
        "스칼라 열화 BC  (Yu–Cioffi 식 (4),  "
        rf"$\alpha={alpha:g}$,  $\sigma_2^2/\sigma_1^2={sigma2_over_sigma1:g}$)"
    )
    left.set_xlabel(r"SINR   $P/\sigma_1^2$   [dB]")
    left.set_ylabel("Capacity  [bits / 실수 차원]")
    left.set_xlim(sinr_min_db, sinr_max_db)
    left.set_ylim(bottom=0.0)
    left.grid(True, alpha=0.35)
    left.legend(loc="upper left", fontsize=8, framealpha=0.92, title=r"$R_i=\frac{1}{2}\log_2(1+\mathrm{SINR}_i)$")

    right = axes[1]
    right.plot(sinr_db, vector_dpc, color=blue, lw=2.2, label="DPC 합용량")
    right.plot(sinr_db, vector_zf, color=orange, lw=1.8, label="ZF 빔포밍")
    right.plot(sinr_db, vector_tdma, color=green, lw=1.8, label="TDMA (균등 시간)")
    right.plot(sinr_db, vector_best, color=purple, lw=1.6, ls="--", label="최강 사용자만 전송")
    paper_db = 10.0 * np.log10(5.0)
    paper_bits = PAPER_APPENDIX_NATS / np.log(2.0)
    right.scatter(
        [paper_db],
        [paper_bits],
        s=46,
        color="#C0392B",
        zorder=5,
        label=r"논문 부록  $P=5$",
    )
    right.annotate(
        f"2.895 nats\n= {paper_bits:.3f} bits",
        xy=(paper_db, paper_bits),
        xytext=(paper_db + 3.2, paper_bits - 2.4),
        fontsize=8,
        color="#C0392B",
        arrowprops={"arrowstyle": "->", "color": "#C0392B", "lw": 0.8},
    )
    right.set_title("벡터 BC 합용량  (Theorem 3, 부록 채널)")
    right.set_xlabel(r"SINR   $P/\sigma^2$   [dB]")
    right.set_ylabel("Capacity  [bits / 실수 차원]")
    right.set_xlim(sinr_min_db, sinr_max_db)
    right.set_ylim(bottom=0.0)
    right.grid(True, alpha=0.35)
    right.legend(loc="upper left", fontsize=8, framealpha=0.92)

    fig.suptitle(
        "Broadcast channel DPC capacity   ·   Yu & Cioffi, IEEE Trans. Inf. Theory, 2004",
        fontsize=12,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def _print_scalar_table(alpha: float, sigma_ratio: float) -> None:
    print()
    print(
        f"스칼라 열화 BC  (α={alpha:g}, σ2²/σ1²={sigma_ratio:g}, "
        "SINR = P/σ1²)"
    )
    header = f"{'SINR[dB]':>10} {'SINR1':>10} {'SINR2':>10} {'R1':>8} {'R2':>8} {'DPC합':>8} {'TIN합':>8} {'합용량':>8}"
    print(header)
    print("-" * len(header))
    for value_db in (-10, 0, 10, 20, 30):
        sinr1, sinr2, sinr1_tin = scalar_bc_sinrs(
            np.array([value_db]), alpha, sigma_ratio
        )
        r1 = float(dpc_rate_from_sinr(sinr1[0]))
        r2 = float(dpc_rate_from_sinr(sinr2[0]))
        tin = float(dpc_rate_from_sinr(sinr1_tin[0])) + r2
        cap = float(dpc_rate_from_sinr(10.0 ** (value_db / 10.0)))
        print(
            f"{value_db:10.1f} {sinr1[0]:10.4f} {sinr2[0]:10.4f} "
            f"{r1:8.3f} {r2:8.3f} {r1 + r2:8.3f} {tin:8.3f} {cap:8.3f}"
        )
    print("전송률 단위는 bits/실수 차원.  R_i = (1/2) log2(1 + SINR_i)")


def _print_vector_table() -> None:
    print()
    print("벡터 BC  (부록 채널 3명 × 송신 3안테나, σ²=1, SINR = P/σ²)")
    header = f"{'SINR[dB]':>10} {'DPC':>8} {'ZF':>8} {'TDMA':>8} {'최강':>8}"
    print(header)
    print("-" * len(header))
    for value_db in (-10, 0, 7, 10, 20, 30):
        power = 10.0 ** (value_db / 10.0)
        dpc, _q = dpc_sum_capacity(PAPER_CHANNEL, power)
        zf = zf_sum_rate(PAPER_CHANNEL, power)
        tdma, best = tdma_rates(PAPER_CHANNEL, power)
        print(f"{value_db:10.1f} {dpc:8.3f} {zf:8.3f} {tdma:8.3f} {best:8.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="BC 채널 DPC 용량 계산 및 SINR-capacity 그래프")
    parser.add_argument("--alpha", type=float, default=0.5, help="강사용자 전력 비율 α")
    parser.add_argument(
        "--sigma-ratio",
        type=float,
        default=4.0,
        help="σ2²/σ1² (약사용자 잡음이 더 큼)",
    )
    parser.add_argument("--sinr-min", type=float, default=-10.0)
    parser.add_argument("--sinr-max", type=float, default=30.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "dpc_capacity_vs_sinr.png",
    )
    args = parser.parse_args()

    nats = verify_paper_appendix()
    print(
        "Yu–Cioffi 부록 검증: "
        f"P=5 에서 DPC 합용량 {nats:.4f} nats "
        f"(논문 {PAPER_APPENDIX_NATS} nats), "
        f"{nats / np.log(2.0):.4f} bits"
    )
    _print_scalar_table(args.alpha, args.sigma_ratio)
    _print_vector_table()
    out = plot_capacity_vs_sinr(
        args.out,
        alpha=args.alpha,
        sigma2_over_sigma1=args.sigma_ratio,
        sinr_min_db=args.sinr_min,
        sinr_max_db=args.sinr_max,
    )
    print()
    print(f"그래프 저장: {out}")


if __name__ == "__main__":
    main()
