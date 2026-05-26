module and_gate(input a, b, output y);
    assign y = a & b;
endmodule

module or_gate(input a, b, output y);
    assign y = a | b;
endmodule

module xor_gate(input a, b, output y);
    assign y = a ^ b;
endmodule

module nand_gate(input a, b, output y);
    assign y = ~(a & b);
endmodule

module nor_gate(input a, b, output y);
    assign y = ~(a | b);
endmodule

module xnor_gate(input a, b, output y);
    assign y = ~(a ^ b);
endmodule

module not_gate(input a, output y);
    assign y = ~a;
endmodule
