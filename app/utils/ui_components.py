"""
app/utils/ui_components.py
Переиспользуемые UI-компоненты для единообразия интерфейса.
"""

import streamlit as st


def render_cta_button(
    title: str,
    subtitle: str,
    button_label: str,
    target_page: str,
    button_key: str,
) -> None:
    """
    Отображает заметную CTA-кнопку с градиентным блоком.

    Args:
        title: Заголовок блока (крупный текст)
        subtitle: Подзаголовок (описание действия)
        button_label: Текст на кнопке
        target_page: Путь к целевой странице (например, "pages/5_dashboard.py")
        button_key: Уникальный ключ для st.button()
    """
    st.divider()

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 2rem;
                    border-radius: 12px;
                    text-align: center;
                    margin: 2rem 0;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
            <h2 style="color: white; margin: 0 0 0.5rem 0; font-size: 1.8rem;">
                {title}
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0 0 1.5rem 0; font-size: 1.1rem;">
                {subtitle}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Преобразуем "pages/5_dashboard.py" в "/2_upload", "/3_mapping" и т.д.
        # для HTML ссылки
        page_num = target_page.replace("pages/", "").replace(".py", "")
        href = f"/{page_num}"
        
        st.markdown(
            f'<a href="{href}" target="_self" style="display:block; width:100%; padding:0.75rem; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; text-align:center; text-decoration:none; border-radius:8px; font-weight:600; font-size:1rem;">{button_label}</a>',
            unsafe_allow_html=True,
        )
