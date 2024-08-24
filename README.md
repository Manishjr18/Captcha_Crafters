# Captcha Crafters 

**Overview**

This project is an advanced CAPTCHA system designed to enhance security through multiple types of CAPTCHA mechanisms, including Text-based CAPTCHA, Image Recognition CAPTCHA, and Audio CAPTCHA. The project is built using a combination of technologies, including React for the frontend, Flask for the backend, and Supabase for data management and authentication.

**Features**

Text-based CAPTCHA: A simple CAPTCHA that generates random strings consisting of lowercase letters and numbers to verify human users.

Image Recognition CAPTCHA: Users are presented with images and must identify the correct images to pass the CAPTCHA challenge.

Audio CAPTCHA: Using Google Text-to-Speech (gTTS) and PyDub, this CAPTCHA generates an audio file that reads out a random string, which users must type in correctly.

API Integration: The CAPTCHA systems are developed as APIs for easy integration with any web application.

User Authentication: Supabase is used for managing user authentication, including OAuth integrations with Google and GitHub.

**Technology Stack**

React: A powerful JavaScript library for building dynamic user interfaces, particularly suited for single-page applications (SPAs).

Flask: A lightweight Python web framework used for developing the backend and handling server-side logic and API requests.

Supabase: An open-source backend-as-a-service platform providing authentication, database, and storage solutions, built on top of PostgreSQL.

gTTS (Google Text-to-Speech): A Python library and CLI tool for interfacing with Google Translate’s text-to-speech API, used for generating audio CAPTCHA challenges.

PyDub: A Python library for manipulating audio files, utilized for generating and processing audio CAPTCHAs.

PostgreSQL: A robust, open-source relational database system, managed by Supabase to store user data and CAPTCHA information.

**Why These Technologies?**

React: Offers efficient UI updates and a component-based architecture, making it ideal for dynamic and responsive web applications.

Flask: Provides simplicity and flexibility for developing APIs and managing backend logic with Python.

Supabase: Streamlines the process of adding authentication and database management with its easy-to-use interface and integration capabilities.

gTTS and PyDub: These libraries simplify the generation and manipulation of audio files, essential for creating accessible CAPTCHAs.

**Usage**

Access the application via the frontend, where users can sign up, log in, and experience the different CAPTCHA challenges.
APIs can be used in external projects by sending requests to the Flask backend.

**Future Enhancements**

Implementing more CAPTCHA types to enhance security.
Improving the user interface for better accessibility and usability.
Adding more customization options for CAPTCHA difficulty and appearance.

**Contributing**

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or new features.
