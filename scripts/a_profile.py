from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "source"


def profile_csv(filename: str) -> None:
    path = DATA_DIR / filename
    df = pd.read_csv(path)

    print("=" * 80)
    print(f"파일: {filename}")
    print(f"행 수: {len(df):,}")
    print(f"열 수: {len(df.columns)}")
    print(f"완전 중복 행: {df.duplicated().sum():,}건")

    print("\n[컬럼별 프로파일]")

    for column in df.columns:
        series = df[column]

        missing_count = series.isna().sum()
        missing_ratio = missing_count / len(df) * 100
        unique_count = series.nunique(dropna=True)

        print("\n" + "-" * 60)
        print(f"컬럼: {column}")
        print(f"dtype: {series.dtype}")
        print(f"결측: {missing_count:,}건 ({missing_ratio:.1f}%)")
        print(f"고유값: {unique_count:,}개")

        sample_values = series.dropna().astype(str).unique()[:5]

        print("샘플:")
        for value in sample_values:
            print(f"  - {value}")

        # 값의 종류가 적은 컬럼은 전체 분포 출력
        if unique_count <= 20:
            print("값 분포:")
            print(series.value_counts(dropna=False).to_string())

        # 숫자 컬럼은 기본 통계 출력
        if pd.api.types.is_numeric_dtype(series):
            print("숫자 통계:")
            print(series.describe().to_string())

    print()


def main() -> None:
    files = [
        "jira_issues.csv",
        "jira_worklog.csv",
        "md_baseline_v0.csv",
        "calendar.csv",
        "people.csv",
    ]

    for filename in files:
        profile_csv(filename)


if __name__ == "__main__":
    main()