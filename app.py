import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- 1. AI 모델 및 보안 환경변수 설정 ---
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    API_KEY = "여기에_발급받은_API_KEY를_입력하세요" 

if not API_KEY or API_KEY.startswith("여기에"):
    st.error("Streamlit Cloud의 Settings -> Secrets에 'GEMINI_API_KEY'가 올바르게 등록되지 않았습니다.")
    st.stop()

genai.configure(api_key=API_KEY)

# 네트워크 버그가 있는 2.5 대신 안정화된 2.0 모델 사용
model = genai.GenerativeModel(model_name='gemini-2.0-flash-lite')

# --- 2. 모바일 최적화 화면 설정 ---
st.set_page_config(
    page_title="AI 오답노트 튜터", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("모바일 AI 오답노트 튜터")
st.caption("과목별 기출분석부터 이해할 때까지 이어지는 1:1 과외")

# --- 3. 세션 상태 관리 초기화 ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "step" not in st.session_state:
    st.session_state.step = "upload" 
if "current_image" not in st.session_state:
    st.session_state.current_image = None
if "subject" not in st.session_state:
    st.session_state.subject = "수학"
if "num_questions" not in st.session_state:
    st.session_state.num_questions = 1

# --- 4. 워크플로우 구현 ---

# [1단계] 문제 업로드 및 설정 화면
if st.session_state.step == "upload":
    st.subheader("1. 문제 등록하기")
    
    st.session_state.subject = st.selectbox("과목 선택", ["국어", "수학", "영어"])
    uploaded_file = st.file_uploader("문제 사진 촬영 또는 첨부", type=['jpg', 'jpeg', 'png'])
    
    user_reason = st.text_area(
        "내가 생각한 오답 이유 (풀이 과정)", 
        placeholder="예: 미분할 때 상수를 누락함 / 단어 뜻을 반대로 해석함"
    )
    
    st.session_state.num_questions = st.slider("연습할 유사 문제 개수", min_value=1, max_value=3, value=1)
    
    if st.button("분석 및 튜터링 시작", use_container_width=True):
        if uploaded_file is not None and user_reason:
            with st.spinner("AI 튜터가 문제를 분석하고 있습니다..."):
                img = Image.open(uploaded_file)
                st.session_state.current_image = img
                
                prompt = f"""
                너는 대한민국 고등학생을 가르치는 전문 {st.session_state.subject} 튜터야.
                사용자가 업로드한 문제 이미지를 텍스트로 정확히 변환하여 보여주고, 정답을 명시해줘.
                그 후, 사용자가 작성한 오답 이유인 "{user_reason}"를 분석하여 실제 정석 풀이 프로세스와 비교해 어느 단계에서 논리적 오류나 개념 착각이 일어났는지 정확하게 지적해줘.
                마지막에는 일방적인 설명을 끝내지 말고, 학생이 이해했는지 점검하는 간단한 질문을 던져줘.
                수학 수식의 경우 반드시 $inline$ 또는 $$display$$ LaTeX 형식을 사용하여 가독성을 높여줘.
                """
                
                try:
                    # 무한 로딩 방지를 위해 request_options로 명시적 타임아웃(30초) 설정
                    response = model.generate_content(
                        [prompt, img], 
                        request_options={"timeout": 30.0}
                    )
                    st.session_state.chat_history.append({"role": "ai", "text": response.text})
                    st.session_state.step = "tutoring"
                    st.rerun()
                except Exception as e:
                    st.error(f"구글 API 통신 중 오류가 발생했습니다. 오류 내용: {e}")
        else:
            st.warning("사진과 오답 이유를 모두 입력해주세요.")

# [2단계] 1:1 대화식 튜터링 화면
elif st.session_state.step == "tutoring":
    st.subheader("2. AI 튜터와 오답 분석")
    
    with st.expander("접기/펼치기: 내가 올린 문제 사진", expanded=True):
        st.image(st.session_state.current_image, use_container_width=True)
    
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state.chat_history:
            if chat["role"] == "user":
                st.chat_message("user").write(chat["text"])
            else:
                st.chat_message("assistant").write(chat["text"])
            
    st.markdown("---")
    user_input = st.chat_input("이해가 안 되는 부분을 질문하세요.")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "text": user_input})
        with st.spinner("답변 작성 중..."):
            chat_context = "\n".join([f"{c['role']}: {c['text']}" for c in st.session_state.chat_history[-4:]])
            follow_up_prompt = f"다음은 학생과의 튜터링 대화 맥락이야. 학생의 추가 질문인 '{user_input}'에 대해 친절하게 설명해줘.\n맥락:\n{chat_context}"
            try:
                # 텍스트 요청은 비교적 빠르므로 타임아웃 20초 설정
                response = model.generate_content(
                    follow_up_prompt,
                    request_options={"timeout": 20.0}
                )
                st.session_state.chat_history.append({"role": "ai", "text": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"답변 생성 중 오류가 발생했습니다: {e}")
            
    if st.button("완전히 이해했어요! 유사 문제 받기", use_container_width=True, type="primary"):
        with st.spinner("평가원/교육청 기출문제를 분석 중입니다..."):
            search_prompt = f"""
            너의 내부 지식 베이스를 활용하여, 이전에 제시된 {st.session_state.subject} 문제와 출제 의도, 핵심 개념, 난이도가 가장 유사한 실제 고등학교 전국의 공인 모의고사(평가원, 교육청) 또는 수능 기출문제를 총 {st.session_state.num_questions}개 찾아주거나 이와 동일한 출제 메커니즘을 가진 쌍둥이 문제를 생성해줘.
            반드시 실제 존재했던 기출문제 형식을 유지하여 발문, 선지(1~5번)를 제공하고, 하단에 각 문제별 정답과 명쾌한 해설을 포함시켜줘.
            수식은 $ 또는 $$ 기호를 사용한 LaTeX 형태로 작성해줘.
            """
            try:
                # 기출문제 검색 및 생성은 리소스가 많이 소모되므로 타임아웃 45초 설정
                response = model.generate_content(
                    search_prompt,
                    request_options={"timeout": 45.0}
                )
                st.session_state.chat_history.append({"role": "ai", "text": response.text})
                st.session_state.step = "finished"
                st.rerun()
            except Exception as e:
                st.error(f"유사 기출문제를 가져오는 중 오류가 발생했습니다: {e}")

# [3단계] 유사 문제 제공 및 완료 화면
elif st.session_state.step == "finished":
    st.subheader("3. 맞춤형 유사 기출문제")
    st.write(st.session_state.chat_history[-1]["text"])
    
    if st.button("새로운 문제 오답노트 만들기", use_container_width=True):
        st.session_state.clear()
        st.rerun()
