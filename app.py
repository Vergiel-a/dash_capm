# Importa as bibliotecas
## Shiny
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget
## Gráficos
import plotly.express as px
import plotly.graph_objs as go
## Dados e manipulação
import yfinance as yf
from bcb import sgs
import numpy as np
import pandas as pd

import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS

## Cria função para o card
def card(titulo, valor, width = 3, bg_color = "bg-info", text_color = "text-white"):
        card_ui = ui.div(
             ui.div(
                ui.div(
                        ui.div(ui.h4(titulo), class_ = "card-title"),
                        ui.div(valor, class_ = "card-text"),
                               class_ = "card-body flex-fill"
                ),
                class_ = f"card {text_color} {bg_color}",
                style = "flex-grow:1;margin;margin:5px"
             ),
             class_ = f"col-md-{width} d-flex"
        )
        return card_ui

# Parte 1: Interface do usuário
app_ui = ui.page_fluid(
   ui.panel_title(title = "Dashboard do Modelo CAPM no Python"),
   ui.layout_sidebar(
    ui.panel_sidebar(
        # Texto do sidebar
        ui.p("Escolha as ações brasileiras"),
        # Escolha dos ativos e Pesos do portfólio
        ui.row(
                ui.column(6,
                      ui.input_text(id = "ativo_variavel1",
                                    label = "Escreva o Ativo",
                                    value = "ITSA4.SA"
                      )
                 ),
                 ui.column(5,
                           ui.input_numeric("w1", "Portf. %", 25,
                                            min = 1, max = 100, step = 1))

        ),
        ui.row(
                ui.column(6,
                      ui.input_text(id = "ativo_variavel2",
                                    label = "Escreva o Ativo",
                                    value = "PETR4.SA"
                      )
                 ),
                 ui.column(5,
                           ui.input_numeric("w2", "Portf. %", 25,
                                            min = 1, max = 100, step = 1))

        ),
        ui.row(
                ui.column(6,
                      ui.input_text(id = "ativo_variavel3",
                                    label = "Escreva o Ativo",
                                    value = "VALE3.SA"
                      )
                 ),
                 ui.column(5,
                           ui.input_numeric("w3", "Portf. %", 25,
                                            min = 1, max = 100, step = 1))

        ),
        ui.row(
                ui.column(6,
                      ui.input_text(id = "ativo_variavel4",
                                    label = "Escreva o Ativo",
                                    value = "WEGE3.SA"
                      )
                 ),
                 ui.column(5,
                           ui.input_numeric("w4", "Portf. %", 25,
                                            min = 1, max = 100, step = 1))

        ),
        # Escolhe da Data e Janela da amostra
        ui.row(
            ui.column(7,
                      ui.input_date(id = 'date',
                                    label = 'Data Inicial',
                                    value = "2018-01-01",
                                    format = "yyyy-mm-dd")
                    )
            ),
        # Define o tamanho da janela
        ui.row(
            ui.column(6,
                      ui.input_numeric(id = "window",
                                       label = "Tamanho da Janela",
                                       value = 66,
                                       min = 22,
                                       max = 252)
    
            )    
        ),
        # Botão de ação
        ui.input_action_button("btn", "Clique aqui")
    ),
    # Cria o painel dos gráfios
    ui.panel_main(
                # Cards
                ui.row(
                    ui.output_ui("stock_info_ui")
                  ),
                ui.row(
                    ui.column(6,
                    ui.h5("Portfólio v. Ibovespa"),
                    output_widget("stock_scatter_widget")
                    ),                    
                    ui.column(6,
                    ui.h5("Beta Móvel de Mercado"),
                    output_widget("stock_rol_beta_widget")
                    )
                ),
                ui.row(
                    ui.column(8, {"style": "margin-top: 20px;"},
                              ui.output_text_verbatim("summary_model")
                )
                )
        )
    )
)

# Parte 2: Lógica de servidor
def server(input, output, session):

    # Cálculo e Reatividade
    @reactive.Calc
    @reactive.event(input.btn)
    ## Importa os preços de fechamento ajustados
    def stock():
        tickers = [input.ativo_variavel1(), input.ativo_variavel2(),
                   input.ativo_variavel3(), input.ativo_variavel4()]
        start_date = input.date()
        prices = yf.download(tickers, start = start_date)['Adj Close']
        prices = prices.tz_localize(None)
        return prices
    
    ## Importa dados do CDI
    def cdi():
        cdi = sgs.get({"cdi":12})
        return cdi

    ## Calcula os log retornos
    def log_returns():
         returns = np.log(stock() / stock().shift(1)).dropna()
         return returns
    
    ## Calcula o retorno do portfolio
    def portfolio():
        ### Pesos
        w = np.array([input.w1()/100, input.w2()/100,
                        input.w3()/100, input.w4()/100])
        ### Retorno do portfólio
        portfolio_return = (log_returns() * w).sum(axis = 1)
        
        portfolio_return_excess =               (
                                cdi().merge(pd.DataFrame(portfolio_return, columns = ['portfolio']), left_index = True, right_index = True)
                                .assign(cdi = lambda x: x.cdi / 100,
                                        portfolio_excess = lambda x : x['portfolio'] - x['cdi'])
                                   )

        return portfolio_return_excess
    
    ## Calcula o retorno do Ibovespa
    def ibov_returns():
        start_date = input.date()
        prices_ibov = yf.download('^BVSP', start = start_date)['Adj Close']
        prices_ibov = prices_ibov.tz_localize(None)
        returns_ibov = np.log(prices_ibov / prices_ibov.shift(1)).dropna()

        rf_ibov =  (
                        cdi().merge(pd.DataFrame(returns_ibov), left_index = True, right_index = True)
                        .assign(cdi = lambda x: x.cdi / 100,
                                ibov_excess = lambda x : x['Adj Close'] - x['cdi'])
                        )

        return rf_ibov   
    
    def all_returns():
        all_returns = portfolio().merge(ibov_returns(), left_index = True, right_index = True)
        return all_returns
    
    ## Calcula o Beta da Amostra
    def portfolio_beta():
        beta = sm.OLS.from_formula('portfolio_excess ~ ibov_excess', data = all_returns()).fit()
        return beta
    
    
    ## Calcula o Beta móvel
    def portfolio_rol_beta():
        
        # Especifica o modelo
        mod = RollingOLS.from_formula('portfolio_excess ~ ibov_excess', data = all_returns(), window = input.window())
        # Roda a regressão
        rres = mod.fit()
        # Obtém os parâmetros estimados
        beta_móvel = rres.params
            
        return beta_móvel
    

    @output
    @render_widget
    @reactive.event(input.btn)
    
    def stock_chart_widget():

        fig = px.line(data_frame = all_returns(),
                      x = all_returns().index,
                      y = ['portfolio_excess', 'ibov_excess'],
                      labels = {
                            "x" : "",
                            "value" : ""
                         }                      
                      
                 )
        return go.FigureWidget(fig)
    
    @output
    @render_widget
    @reactive.event(input.btn)
    def stock_scatter_widget():

        fig1 = px.scatter(data_frame = all_returns(),
                      x = 'ibov_excess',
                      y = 'portfolio_excess',
                      labels = {
                            "x" : "",
                            "value" : ""
                         },
                      trendline = 'ols'             
                      
                 )
        return go.FigureWidget(fig1)  

    @output
    @render_widget
    @reactive.event(input.btn)
    def stock_rol_beta_widget():

        fig2 = px.line(data_frame = portfolio_rol_beta(),
                      x = portfolio_rol_beta().index,
                      y = 'ibov_excess',
                      labels = {
                            "x" : "",
                            "value" : ""
                      }
                 )
        return go.FigureWidget(fig2)

    @output
    @render.text()
    @reactive.event(input.btn)

    def summary_model():
       model = portfolio_beta().summary()
       return model

    @output
    @render.ui
    @reactive.event(input.btn)
    
    def stock_info_ui():
        app_ui = ui.row(
             ui.h5("Métricas do Portfólio"),
             card("Beta da Carteira", round(portfolio_beta().params['ibov_excess'], ndigits = 3), bg_color = "bg-dark")
            )

        return app_ui    
    
    @output
    @render.ui
    @reactive.event(input.btn)
    
    def stock_info_ui():
        app_ui = ui.row(
             ui.h5("Métricas do Portfólio"),
             card("Beta da Carteira", round(portfolio_beta().params['ibov_excess'], ndigits = 3), bg_color = "bg-dark")
            )

        return app_ui

# Parte 3: aplicação
app = App(app_ui, server)
